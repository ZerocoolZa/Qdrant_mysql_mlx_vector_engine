#!/usr/bin/env python3
# [@GHOST]{[@file<config.py>][@domain<ModelControlCenter>][@role<registry>][@auth<cascade>][@date<2026-07-03>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<registry>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Model Registry config — defines all available TTS/neural models with metadata, dependencies, and install state.}

import os
import json

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "model_registry.json")

MODELS_BASE_DIR = os.path.expanduser("~/KokoroModels")

MODEL_REGISTRY = [
    {
        "id": "kokoro_fp16",
        "name": "Kokoro 82M FP16",
        "size_mb": 163,
        "description": "Neural TTS model optimized for Apple Silicon (FP16)",
        "platforms": ["mac", "m1", "m2", "m3"],
        "pip": ["onnxruntime", "soundfile", "numpy"],
        "source_url": "https://huggingface.co/anyam12/Kokoro",
        "local_path": os.path.join(MODELS_BASE_DIR, "kokoro_fp16"),
        "status": "not_installed",
        "version": "1.0",
        "category": "Neural TTS",
    },
    {
        "id": "kokoro_q8",
        "name": "Kokoro 82M Q8 Quantized",
        "size_mb": 82,
        "description": "Quantized Kokoro model — smaller footprint, slightly lower quality",
        "platforms": ["mac", "m1", "m2", "m3"],
        "pip": ["onnxruntime", "soundfile", "numpy"],
        "source_url": "https://huggingface.co/anyam12/Kokoro",
        "local_path": os.path.join(MODELS_BASE_DIR, "kokoro_q8"),
        "status": "not_installed",
        "version": "1.0",
        "category": "Neural TTS",
    },
    {
        "id": "edge_tts",
        "name": "Edge Neural TTS (Cloud)",
        "size_mb": 0,
        "description": "Microsoft Edge neural voices via API — no local download needed",
        "platforms": ["mac", "win", "linux"],
        "pip": ["edge-tts"],
        "source_url": "https://pypi.org/project/edge-tts/",
        "local_path": None,
        "status": "installed",
        "version": "latest",
        "category": "Cloud TTS",
    },
    {
        "id": "macos_say",
        "name": "macOS say (System)",
        "size_mb": 0,
        "description": "Built-in macOS TTS voices — no installation required",
        "platforms": ["mac"],
        "pip": [],
        "source_url": None,
        "local_path": None,
        "status": "installed",
        "version": "system",
        "category": "System TTS",
    },
    {
        "id": "coqui_xtts",
        "name": "Coqui XTTS v2",
        "size_mb": 1800,
        "description": "Multilingual neural TTS with voice cloning capability",
        "platforms": ["mac", "win", "linux"],
        "pip": ["TTS", "torch", "soundfile"],
        "source_url": "https://huggingface.co/coqui/XTTS-v2",
        "local_path": os.path.join(MODELS_BASE_DIR, "coqui_xtts"),
        "status": "not_installed",
        "version": "2.0",
        "category": "Neural TTS",
    },
    {
        "id": "bark",
        "name": "Suno Bark",
        "size_mb": 1200,
        "description": "Generative audio model — speech, music, and sound effects",
        "platforms": ["mac", "win", "linux"],
        "pip": ["bark", "torch", "soundfile"],
        "source_url": "https://huggingface.co/suno/bark",
        "local_path": os.path.join(MODELS_BASE_DIR, "bark"),
        "status": "not_installed",
        "version": "1.0",
        "category": "Generative Audio",
    },
]

CATEGORIES = ["All", "Neural TTS", "Cloud TTS", "System TTS", "Generative Audio", "Discovered"]

STATUSES = {
    "installed": ("Installed", "#27ae60"),
    "not_installed": ("Not Installed", "#e74c3c"),
    "deleted": ("Deleted", "#95a5a6"),
    "downloading": ("Downloading...", "#f39c12"),
    "testing": ("Testing...", "#f39c12"),
    "tested_pass": ("Tested OK", "#27ae60"),
    "tested_fail": ("Test Failed", "#e74c3c"),
}

# ═══════════════════════════════════════════════════════════
# THEMES — Multiple themes with high contrast options
# ═══════════════════════════════════════════════════════════

THEMES = {
    "Catppuccin Dark": {
        "bg": "#1e1e2e",
        "surface": "#313244",
        "primary": "#89b4fa",
        "accent": "#f5c2e7",
        "text": "#cdd6f4",
        "text_dim": "#a6adc8",
        "success": "#a6e3a1",
        "danger": "#f38ba8",
        "warning": "#f9e2af",
        "border": "#45475a",
    },
    "High Contrast Dark": {
        "bg": "#000000",
        "surface": "#1a1a1a",
        "primary": "#5599ff",
        "accent": "#ff79c6",
        "text": "#ffffff",
        "text_dim": "#cccccc",
        "success": "#00ff41",
        "danger": "#ff4444",
        "warning": "#ffcc00",
        "border": "#444444",
    },
    "VS Code Dark+": {
        "bg": "#1e1e1e",
        "surface": "#252526",
        "primary": "#0a84ff",
        "accent": "#c586c0",
        "text": "#d4d4d4",
        "text_dim": "#858585",
        "success": "#4ec9b0",
        "danger": "#f48771",
        "warning": "#dcdcaa",
        "border": "#3c3c3c",
    },
    "Dracula": {
        "bg": "#282a36",
        "surface": "#383a4a",
        "primary": "#bd93f9",
        "accent": "#ff79c6",
        "text": "#f8f8f2",
        "text_dim": "#bdc3c3",
        "success": "#50fa7b",
        "danger": "#ff5555",
        "warning": "#f1fa8c",
        "border": "#44475a",
    },
    "Solarized Dark": {
        "bg": "#002b36",
        "surface": "#073642",
        "primary": "#268bd2",
        "accent": "#d33682",
        "text": "#93a1a1",
        "text_dim": "#657b83",
        "success": "#859900",
        "danger": "#dc322f",
        "warning": "#b58900",
        "border": "#586e75",
    },
    "Light": {
        "bg": "#ffffff",
        "surface": "#f5f5f5",
        "primary": "#0066cc",
        "accent": "#cc0099",
        "text": "#1a1a1a",
        "text_dim": "#666666",
        "success": "#008800",
        "danger": "#cc0000",
        "warning": "#cc8800",
        "border": "#cccccc",
    },
    "High Contrast Light": {
        "bg": "#ffffff",
        "surface": "#e8e8e8",
        "primary": "#0000cc",
        "accent": "#cc0066",
        "text": "#000000",
        "text_dim": "#333333",
        "success": "#006600",
        "danger": "#cc0000",
        "warning": "#cc6600",
        "border": "#666666",
    },
}

# Default theme (used on first load)
THEME = THEMES["Catppuccin Dark"]

WINDOW_TITLE = "Model Control Center"
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 600

SCANNER_CONFIG = {
    "directories": [
        os.path.expanduser("~/KokoroModels"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Library/Application Support"),
        os.path.expanduser("~/.cache"),
        os.path.expanduser("~/models"),
        os.path.expanduser("~/.ollama"),
        os.path.expanduser("~/.lmstudio"),
        os.path.expanduser("~/.cache/huggingface"),
        os.path.expanduser("~/.cache/torch"),
        os.path.expanduser("~/Library/Developer/CoreML/MLData"),
        os.path.expanduser("~/Library/Application Support/MLX"),
        os.path.expanduser("~/.mlx"),
        os.path.expanduser("~/Library/Caches/com.apple.CoreML"),
        os.path.expanduser("~/Library/Application Support/llama.cpp"),
        os.path.dirname(__file__),
    ],
    "extensions": [
        # ONNX
        ".onnx", ".ort",
        # CoreML
        ".mlmodel", ".mlpackage", ".mlmodelc",
        # PyTorch
        ".pt", ".pth", ".bin", ".ckpt", ".safetensors", ".torchscript", ".ts",
        # MLX (Apple Silicon)
        ".mlx", ".npz",
        # llama.cpp / GGML
        ".gguf", ".ggml", ".ggjt",
        # TensorFlow / Keras
        ".tflite", ".h5", ".keras", ".pb", ".tfrecord", ".savedmodel",
        # JAX / Flax
        ".msgpack", ".flax",
        # General / Other
        ".weights", ".model", ".param", ".engine", ".pkl", ".pickle",
        ".npy", ".joblib", ".dat", ".mar", ".tar", ".zip",
    ],
    "max_depth": 4,
    "min_file_size_mb": 1,
    "skip_hidden": True,
}

IDENTIFIER_CONFIG = {
    "magic_bytes": {
        "onnx": b"\x08\x07",
        "safetensors": b"H\x00\x00\x00{\"",
        "gguf": b"GGUF",
        "ggml": b"ggml",
        "pickle": b"\x80\x02",
        "pickle3": b"\x80\x03",
        "pickle4": b"\x80\x04",
        "pickle5": b"\x80\x05",
        "numpy": b"\x93NUMPY",
        "zip": b"PK\x03\x04",
        "tar": b"ustar",
        "hdf5": b"\x89HDF\r\n\x1a\n",
        "tflite": b"TFL3",
        "msgpack": b"\x85",
    },
    "extension_to_framework": {
        ".onnx": "ONNX",
        ".ort": "ONNX",
        ".mlmodel": "CoreML",
        ".mlpackage": "CoreML",
        ".mlmodelc": "CoreML",
        ".pt": "PyTorch",
        ".pth": "PyTorch",
        ".bin": "PyTorch",
        ".ckpt": "PyTorch",
        ".safetensors": "SafeTensors",
        ".torchscript": "PyTorch",
        ".ts": "PyTorch",
        ".mlx": "MLX",
        ".npz": "NumPy",
        ".gguf": "llama.cpp",
        ".ggml": "llama.cpp",
        ".ggjt": "llama.cpp",
        ".tflite": "TensorFlow Lite",
        ".h5": "Keras/HDF5",
        ".keras": "Keras",
        ".pb": "TensorFlow",
        ".tfrecord": "TensorFlow",
        ".savedmodel": "TensorFlow",
        ".msgpack": "JAX/Flax",
        ".flax": "JAX/Flax",
        ".weights": "Weights",
        ".model": "Unknown",
        ".param": "Parameters",
        ".engine": "TensorRT",
        ".pkl": "Pickle",
        ".pickle": "Pickle",
        ".npy": "NumPy",
        ".joblib": "Joblib",
        ".dat": "Data",
        ".mar": "TorchServe",
        ".tar": "Archive",
        ".zip": "Archive",
    },
    "framework_categories": {
        "ONNX": "ONNX Runtime",
        "CoreML": "Apple CoreML",
        "PyTorch": "PyTorch",
        "SafeTensors": "SafeTensors",
        "MLX": "Apple MLX",
        "NumPy": "NumPy Arrays",
        "llama.cpp": "llama.cpp / GGUF",
        "TensorFlow Lite": "TensorFlow Lite",
        "Keras": "Keras",
        "Keras/HDF5": "Keras/HDF5",
        "TensorFlow": "TensorFlow",
        "JAX/Flax": "JAX/Flax",
        "TensorRT": "TensorRT",
        "Pickle": "Serialized Object",
        "Joblib": "Serialized Object",
        "TorchServe": "TorchServe Archive",
        "Archive": "Archive Bundle",
        "Weights": "Raw Weights",
        "Parameters": "Parameter File",
        "Data": "Data File",
        "Unknown": "Unknown Format",
    },
    "read_header_bytes": 16,
    "extract_safetensors_metadata": True,
    "extract_gguf_metadata": True,
}

PACKAGE_CONFIG = {
    "framework_packages": {
        "ONNX": ["onnxruntime"],
        "CoreML": ["coremltools"],
        "PyTorch": ["torch", "torchvision"],
        "SafeTensors": ["safetensors", "torch"],
        "MLX": ["mlx", "mlx-lm"],
        "NumPy": ["numpy"],
        "llama.cpp": ["llama-cpp-python"],
        "TensorFlow Lite": ["tflite-runtime"],
        "TensorFlow": ["tensorflow"],
        "Keras": ["tensorflow", "keras"],
        "Keras/HDF5": ["tensorflow", "h5py"],
        "JAX/Flax": ["jax", "flax"],
        "TensorRT": ["tensorrt"],
        "Pickle": ["torch"],
        "Joblib": ["joblib", "scikit-learn"],
        "TorchServe": ["torchserve", "torch-model-archiver"],
    },
    "package_check_commands": {
        "onnxruntime": "import onnxruntime",
        "coremltools": "import coremltools",
        "torch": "import torch",
        "torchvision": "import torchvision",
        "safetensors": "import safetensors",
        "mlx": "import mlx",
        "mlx-lm": "import mlx_lm",
        "numpy": "import numpy",
        "llama-cpp-python": "import llama_cpp",
        "tflite-runtime": "import tflite_runtime",
        "tensorflow": "import tensorflow",
        "keras": "import keras",
        "h5py": "import h5py",
        "jax": "import jax",
        "flax": "import flax",
        "tensorrt": "import tensorrt",
        "joblib": "import joblib",
        "scikit-learn": "import sklearn",
        "torchserve": "import ts",
        "torch-model-archiver": "import model_archiver",
    },
    "pip_command": "pip3",
    "pip_install_flags": ["install", "--quiet"],
    "pip_uninstall_flags": ["uninstall", "--quiet", "--yes"],
}

TESTER_CONFIG = {
    "timeout_seconds": 30,
    "max_file_size_mb_for_full_test": 500,
    "test_load_imports": True,
    "test_safetensors_header": True,
    "test_gguf_header": True,
    "test_onnx_load": False,
    "test_coreml_load": False,
    "test_pytorch_load": False,
    "test_tflite_load": False,
}

HARDWARE_CONFIG = {
    "ram_safety_margin_mb": 512,
    "disk_safety_margin_mb": 1024,
    "model_ram_multiplier": 1.5,
    "check_gpu": True,
    "check_neural_engine": True,
    "disk_check_path": os.path.expanduser("~"),
    "large_model_threshold_mb": 5000,
    "very_large_model_threshold_mb": 20000,
    "low_ram_threshold_mb": 8000,
}

TOOLTIPS = {
    "install": "Install selected model (pip dependencies + download if needed)",
    "uninstall": "Mark model as not installed (keeps files on disk)",
    "delete": "Delete model files from disk and mark as deleted",
    "restore": "Restore a deleted model back to installed state",
    "refresh": "Reload model list from registry",
    "search": "Filter models by name, description, or category",
    "category": "Filter models by category",
    "scan": "Scan your Mac for existing model files (.onnx, .mlmodel, .bin, .pt, .safetensors, etc.)",
    "test": "Run validation tests on the selected model (header check, structure, load test)",
    "theme": "Switch between color themes (Dark, Light, High Contrast, etc.)",
}

STATUS_MESSAGES = {
    "ready": "Ready",
    "installing": "Installing model...",
    "uninstalling": "Uninstalling model...",
    "deleting": "Deleting model files...",
    "restoring": "Restoring model...",
    "installed": "Model installed successfully",
    "uninstalled": "Model uninstalled",
    "deleted": "Model deleted",
    "restored": "Model restored",
    "error": "Error: %s",
    "no_selection": "No model selected",
    "scanning": "Scanning for models...",
    "scan_done": "Scan complete — found %d models",
    "scan_empty": "Scan complete — no models found",
    "testing": "Testing model...",
    "test_pass": "Model test PASSED — all checks passed",
    "test_fail": "Model test FAILED — see details",
    "test_no_file": "No model file to test — install or scan first",
    "theme_changed": "Theme changed to: %s",
}


def load_registry():
    """Load registry from JSON if it exists, otherwise return defaults."""
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return MODEL_REGISTRY


def save_registry(registry):
    """Persist registry state to JSON."""
    try:
        with open(REGISTRY_PATH, "w") as f:
            json.dump(registry, f, indent=2)
        return True
    except IOError:
        return False
