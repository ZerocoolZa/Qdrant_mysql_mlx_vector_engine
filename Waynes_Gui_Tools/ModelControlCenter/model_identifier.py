#!/usr/bin/env python3
# [@GHOST]{[@file<model_identifier.py>][@domain<ModelControlCenter>][@role<identifier>][@auth<cascade>][@date<2026-07-03>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<identifier>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{ModelIdentifier — reads file headers and magic bytes to confirm model format, extract metadata, and categorize by framework. Goes beyond extension guessing.}

import os
import json
import struct

from config import IDENTIFIER_CONFIG


class ModelIdentifier:
    """Identifies model files by reading magic bytes and extracting metadata."""

    def __init__(self):
        self.magic_bytes = IDENTIFIER_CONFIG["magic_bytes"]
        self.ext_map = IDENTIFIER_CONFIG["extension_to_framework"]
        self.framework_categories = IDENTIFIER_CONFIG["framework_categories"]
        self.header_size = IDENTIFIER_CONFIG["read_header_bytes"]
        self.extract_safetensors = IDENTIFIER_CONFIG["extract_safetensors_metadata"]
        self.extract_gguf = IDENTIFIER_CONFIG["extract_gguf_metadata"]

    def identify(self, file_path):
        """Identify a model file. Returns dict with framework, format_confirmed, metadata."""
        ext = os.path.splitext(file_path)[1].lower()
        framework = self.ext_map.get(ext, "Unknown")
        category = self.framework_categories.get(framework, "Unknown Format")

        result = {
            "file_path": file_path,
            "extension": ext,
            "framework": framework,
            "category": category,
            "format_confirmed": False,
            "magic_match": None,
            "metadata": {},
        }

        header = self.read_header(file_path)
        if header:
            magic_name = self.match_magic(header)
            if magic_name:
                result["magic_match"] = magic_name
                result["format_confirmed"] = True
                if magic_name in ("pickle", "pickle3", "pickle4", "pickle5"):
                    result["framework"] = "Pickle"
                elif magic_name == "safetensors":
                    result["framework"] = "SafeTensors"
                elif magic_name == "gguf":
                    result["framework"] = "llama.cpp"
                elif magic_name == "ggml":
                    result["framework"] = "llama.cpp"
                elif magic_name == "onnx":
                    result["framework"] = "ONNX"
                elif magic_name == "hdf5":
                    result["framework"] = "Keras/HDF5"
                elif magic_name == "tflite":
                    result["framework"] = "TensorFlow Lite"
                elif magic_name == "numpy":
                    result["framework"] = "NumPy"
                elif magic_name == "zip":
                    result["framework"] = self.detect_zip_framework(file_path)
                elif magic_name == "msgpack":
                    result["framework"] = "JAX/Flax"

        if self.extract_safetensors and result["framework"] == "SafeTensors":
            result["metadata"] = self.extract_safetensors_meta(file_path)

        if self.extract_gguf and result["framework"] == "llama.cpp":
            result["metadata"] = self.extract_gguf_meta(file_path)

        result["category"] = self.framework_categories.get(result["framework"], "Unknown Format")
        return result

    def read_header(self, file_path):
        """Read first N bytes from file for magic byte matching."""
        try:
            with open(file_path, "rb") as f:
                return f.read(self.header_size)
        except (OSError, IOError):
            return None

    def match_magic(self, header):
        """Match header bytes against known magic signatures."""
        for name, sig in self.magic_bytes.items():
            if header.startswith(sig):
                return name
        return None

    def detect_zip_framework(self, file_path):
        """Try to determine if a zip archive is a Keras model, TorchServe MAR, or plain archive."""
        import zipfile
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()
                if any("config.json" in n for n in names):
                    return "Keras"
                if any("MAR-INF" in n for n in names):
                    return "TorchServe"
                if any(".pt" in n or "pytorch_model" in n for n in names):
                    return "PyTorch"
                return "Archive"
        except (zipfile.BadZipFile, OSError):
            return "Archive"

    def extract_safetensors_meta(self, file_path):
        """Read the JSON header from a safetensors file."""
        try:
            with open(file_path, "rb") as f:
                header_len_bytes = f.read(8)
                header_len = struct.unpack("<Q", header_len_bytes)[0]
                header_json = f.read(header_len).decode("utf-8")
                parsed = json.loads(header_json)
                tensors = [k for k in parsed.keys() if k != "__metadata__"]
                meta = parsed.get("__metadata__", {})
                return {
                    "tensor_count": len(tensors),
                    "tensor_names": tensors[:10],
                    "metadata_fields": list(meta.keys()) if meta else [],
                    "format": "safetensors",
                }
        except (OSError, IOError, struct.error, json.JSONDecodeError, UnicodeDecodeError):
            return {"format": "safetensors", "error": "could not read header"}

    def extract_gguf_meta(self, file_path):
        """Read GGUF header for version and tensor count."""
        try:
            with open(file_path, "rb") as f:
                magic = f.read(4)
                if magic != b"GGUF":
                    return {"format": "gguf", "error": "not a valid GGUF file"}
                version = struct.unpack("<I", f.read(4))[0]
                tensor_count = struct.unpack("<Q", f.read(8))[0]
                kv_count = struct.unpack("<Q", f.read(8))[0]
                return {
                    "format": "gguf",
                    "version": version,
                    "tensor_count": tensor_count,
                    "metadata_kv_count": kv_count,
                }
        except (OSError, IOError, struct.error):
            return {"format": "gguf", "error": "could not read header"}

    def identify_batch(self, file_paths):
        """Identify multiple files. Returns list of identification dicts."""
        results = []
        for fp in file_paths:
            results.append(self.identify(fp))
        return results

    def get_supported_frameworks(self):
        """Return list of all frameworks the identifier can detect."""
        return sorted(set(self.ext_map.values()))
