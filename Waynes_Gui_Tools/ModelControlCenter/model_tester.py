#!/usr/bin/env python3
# [@GHOST]{[@file<model_tester.py>][@domain<ModelControlCenter>][@role<tester>][@auth<cascade>][@date<2026-07-03>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<tester>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{ModelTester — validates model files by checking structure, headers, and optionally loading them. Returns test results with pass/fail and diagnostics.}

import os
import json
import struct
import subprocess
import sys

from config import TESTER_CONFIG


class ModelTester:
    """Tests model files for validity — header checks, structure, optional load tests."""

    def __init__(self):
        self.timeout = TESTER_CONFIG["timeout_seconds"]
        self.max_full_test_mb = TESTER_CONFIG["max_file_size_mb_for_full_test"]
        self.test_imports = TESTER_CONFIG["test_load_imports"]
        self.test_safetensors = TESTER_CONFIG["test_safetensors_header"]
        self.test_gguf = TESTER_CONFIG["test_gguf_header"]
        self.test_onnx_load = TESTER_CONFIG["test_onnx_load"]
        self.test_coreml_load = TESTER_CONFIG["test_coreml_load"]
        self.test_pytorch_load = TESTER_CONFIG["test_pytorch_load"]
        self.test_tflite_load = TESTER_CONFIG["test_tflite_load"]

    def test(self, file_path, framework=None):
        """Run all applicable tests on a model file. Returns result dict."""
        result = {
            "file_path": file_path,
            "framework": framework,
            "tests_passed": [],
            "tests_failed": [],
            "warnings": [],
            "overall_pass": False,
            "details": {},
        }

        if not os.path.exists(file_path):
            result["tests_failed"].append("file_exists")
            return result
        result["tests_passed"].append("file_exists")

        file_size = os.path.getsize(file_path)
        size_mb = file_size // (1024 * 1024)
        result["details"]["size_mb"] = size_mb

        if size_mb == 0:
            result["tests_failed"].append("non_empty")
            return result
        result["tests_passed"].append("non_empty")

        if framework == "SafeTensors" and self.test_safetensors:
            self.test_safetensors_file(file_path, result)
        elif framework == "llama.cpp" and self.test_gguf:
            self.test_gguf_file(file_path, result)
        elif framework == "ONNX" and self.test_onnx_load:
            self.test_onnx_file(file_path, result)
        elif framework == "CoreML" and self.test_coreml_load:
            self.test_coreml_file(file_path, result)
        elif framework == "PyTorch" and self.test_pytorch_load:
            self.test_pytorch_file(file_path, result)
        elif framework == "TensorFlow Lite" and self.test_tflite_load:
            self.test_tflite_file(file_path, result)
        else:
            self.test_basic_structure(file_path, result)

        if self.test_imports and framework:
            self.test_framework_imports(framework, result)

        result["overall_pass"] = len(result["tests_failed"]) == 0
        return result

    def test_safetensors_file(self, file_path, result):
        """Validate safetensors header structure."""
        try:
            with open(file_path, "rb") as f:
                header_len_bytes = f.read(8)
                if len(header_len_bytes) < 8:
                    result["tests_failed"].append("safetensors_header_length")
                    return
                header_len = struct.unpack("<Q", header_len_bytes)[0]
                if header_len > 100 * 1024 * 1024:
                    result["warnings"].append("safetensors_header_very_large")
                header_json = f.read(header_len).decode("utf-8")
                parsed = json.loads(header_json)
                tensor_keys = [k for k in parsed if k != "__metadata__"]
                result["details"]["tensor_count"] = len(tensor_keys)
                result["tests_passed"].append("safetensors_header_valid")
        except (OSError, struct.error, json.JSONDecodeError, UnicodeDecodeError) as e:
            result["tests_failed"].append("safetensors_header_invalid")
            result["details"]["safetensors_error"] = str(e)

    def test_gguf_file(self, file_path, result):
        """Validate GGUF binary header."""
        try:
            with open(file_path, "rb") as f:
                magic = f.read(4)
                if magic != b"GGUF":
                    result["tests_failed"].append("gguf_magic_mismatch")
                    return
                version = struct.unpack("<I", f.read(4))[0]
                tensor_count = struct.unpack("<Q", f.read(8))[0]
                kv_count = struct.unpack("<Q", f.read(8))[0]
                result["details"]["gguf_version"] = version
                result["details"]["gguf_tensor_count"] = tensor_count
                result["details"]["gguf_kv_count"] = kv_count
                result["tests_passed"].append("gguf_header_valid")
        except (OSError, struct.error) as e:
            result["tests_failed"].append("gguf_header_invalid")
            result["details"]["gguf_error"] = str(e)

    def test_onnx_file(self, file_path, result):
        """Attempt to load ONNX model (requires onnxruntime)."""
        script = "import onnx; m = onnx.load('%s'); print('OK')" % file_path.replace("'", "\\'")
        self.run_load_test("onnx_load", script, result)

    def test_coreml_file(self, file_path, result):
        """Attempt to load CoreML model (requires coremltools)."""
        script = "import coremltools as ct; m = ct.models.MLModel('%s'); print('OK')" % file_path.replace("'", "\\'")
        self.run_load_test("coreml_load", script, result)

    def test_pytorch_file(self, file_path, result):
        """Attempt to load PyTorch model (requires torch)."""
        script = "import torch; m = torch.load('%s', map_location='cpu'); print('OK')" % file_path.replace("'", "\\'")
        self.run_load_test("pytorch_load", script, result)

    def test_tflite_file(self, file_path, result):
        """Attempt to load TFLite model (requires tflite-runtime)."""
        script = "import tflite_runtime.interpreter as t; i = t.Interpreter('%s'); i.allocate_tensors(); print('OK')" % file_path.replace("'", "\\'")
        self.run_load_test("tflite_load", script, result)

    def test_basic_structure(self, file_path, result):
        """Basic structural check for unknown frameworks — read first bytes, check not all zeros."""
        try:
            with open(file_path, "rb") as f:
                header = f.read(64)
            if not any(header):
                result["tests_failed"].append("file_all_zeros")
                return
            result["tests_passed"].append("basic_structure")
        except OSError:
            result["tests_failed"].append("read_error")

    def test_framework_imports(self, framework, result):
        """Check if the required Python packages for a framework are importable."""
        from model_package_installer import ModelPackageInstaller
        installer = ModelPackageInstaller()
        check = installer.check_framework_packages(framework)
        result["details"]["packages"] = check
        if check["all_installed"]:
            result["tests_passed"].append("framework_packages_available")
        else:
            result["tests_failed"].append("framework_packages_missing")
            result["warnings"].append("missing: %s" % ", ".join(check["missing"]))

    def run_load_test(self, test_name, script, result):
        """Run a load test script in a subprocess with timeout."""
        try:
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if proc.returncode == 0:
                result["tests_passed"].append(test_name)
            else:
                result["tests_failed"].append(test_name)
                result["details"][test_name + "_error"] = proc.stderr.strip()[:200]
        except subprocess.TimeoutExpired:
            result["tests_failed"].append(test_name + "_timeout")
        except OSError as e:
            result["tests_failed"].append(test_name + "_exec_error")
            result["details"][test_name + "_error"] = str(e)

    def test_batch(self, file_paths, frameworks=None):
        """Test multiple files. Returns list of result dicts."""
        results = []
        for i, fp in enumerate(file_paths):
            fw = frameworks[i] if frameworks else None
            results.append(self.test(fp, framework=fw))
        return results
