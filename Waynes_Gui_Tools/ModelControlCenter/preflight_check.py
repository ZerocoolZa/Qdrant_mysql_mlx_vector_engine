#!/usr/bin/env python3
# [@GHOST]{[@file<preflight_check.py>][@domain<ModelControlCenter>][@role<preflight>][@auth<devin>][@date<2026-07-04>][@ver<1.0>][@context<Pre-flight checks before loading any AI model. Verifies backend installed, model available, RAM sufficient, disk space, service running. Prevents crashes and hangs from missing dependencies.>]}
# [@VBSTYLE]{[@auth<devin>][@role<preflight>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{PreflightCheck — validates environment before model load. Checks: backend package importable, model downloaded/available, RAM sufficient, disk space available, Ollama service running. Returns structured result with pass/fail per check and human-readable messages.}
# [@FILEID]{preflight_check.py}
# [@CLASS]{PreflightCheck}
# [@METHOD]{Run, CheckBackend, CheckModelAvailable, CheckRAM, CheckDiskSpace, CheckOllamaRunning, FormatResult}

import os
import sys
import shutil
import subprocess
import urllib.request
import urllib.error
import json


class PreflightCheck:
    """Pre-flight validation before loading any AI model. Prevents crashes."""

    def __init__(self):
        self.checks = []
        self.results = []

    def Run(self, command, params=None):
        """Dispatch: run pre-flight checks for a given backend + model.
        command = "check_all" | "check_backend" | "check_model" | "check_ram" | "check_disk" | "check_ollama"
        params = {"backend": "mlx"|"ollama"|"llama_cpp", "model_name": str, "model_size_mb": int}
        Returns Tuple3: (1, results_list, None) or (0, None, (code, desc, 0))
        """
        if command == "check_all":
            return self.check_all(params or {})
        elif command == "check_backend":
            return self.check_backend(params or {})
        elif command == "check_model":
            return self.check_model_available(params or {})
        elif command == "check_ram":
            return self.check_ram(params or {})
        elif command == "check_disk":
            return self.check_disk_space(params or {})
        elif command == "check_ollama":
            return self.check_ollama_running(params or {})
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: %s" % command, 0))

    def check_all(self, params):
        """Run all applicable pre-flight checks. Returns (1, results, None)."""
        backend = params.get("backend", "mlx")
        model_name = params.get("model_name", "")
        model_size_mb = params.get("model_size_mb", 0)

        self.results = []

        self.results.append(self.check_backend({"backend": backend}))
        self.results.append(self.check_model_available({"backend": backend, "model_name": model_name}))
        self.results.append(self.check_ram({"model_size_mb": model_size_mb}))
        self.results.append(self.check_disk_space({"model_size_mb": model_size_mb}))

        if backend == "ollama":
            self.results.append(self.check_ollama_running({}))

        return (1, self.results, None)

    def check_backend(self, params):
        """Check if the backend Python package is importable."""
        backend = params.get("backend", "mlx")
        packages = {
            "mlx": "mlx_lm",
            "llama_cpp": "llama_cpp",
            "ollama": None,
        }

        pkg = packages.get(backend)
        if pkg is None:
            if backend == "ollama":
                return {"check": "backend", "pass": True, "message": "Ollama uses HTTP API — no Python package needed"}
            return {"check": "backend", "pass": False, "message": "Unknown backend: %s" % backend}

        try:
            __import__(pkg)
            return {"check": "backend", "pass": True, "message": "%s is installed and importable" % pkg}
        except ImportError:
            install_cmd = {
                "mlx_lm": "pip3 install mlx-lm",
                "llama_cpp": "pip3 install llama-cpp-python",
            }
            cmd = install_cmd.get(pkg, "pip3 install %s" % pkg)
            return {"check": "backend", "pass": False, "message": "%s NOT installed. Run: %s" % (pkg, cmd)}

    def check_model_available(self, params):
        """Check if the model is downloaded locally or available for download."""
        backend = params.get("backend", "mlx")
        model_name = params.get("model_name", "")

        if not model_name:
            return {"check": "model", "pass": False, "message": "No model name specified"}

        if backend == "mlx":
            return self._check_mlx_model(model_name)
        elif backend == "ollama":
            return self._check_ollama_model(model_name)
        elif backend == "llama_cpp":
            return self._check_gguf_model(model_name)
        return {"check": "model", "pass": False, "message": "Unknown backend for model check"}

    def _check_mlx_model(self, model_name):
        """Check if MLX model is cached in HuggingFace cache."""
        cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
        if os.path.exists(cache_dir):
            model_dir_name = "models--" + model_name.replace("/", "--")
            model_cache_path = os.path.join(cache_dir, model_dir_name)
            if os.path.exists(model_cache_path):
                snapshots = os.path.join(model_cache_path, "snapshots")
                if os.path.exists(snapshots):
                    snapshots_list = os.listdir(snapshots)
                    if snapshots_list:
                        return {"check": "model", "pass": True, "message": "Model cached locally at %s" % model_cache_path}
                return {"check": "model", "pass": True, "message": "Model directory exists (may be partial download)"}
            return {"check": "model", "pass": False, "message": "Model NOT cached. Will download from HuggingFace (may take a while)"}
        return {"check": "model", "pass": False, "message": "HuggingFace cache dir not found. Model will be downloaded."}

    def _check_ollama_model(self, model_name):
        """Check if Ollama has the model pulled."""
        try:
            url = "http://localhost:11434/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                for m in models:
                    if model_name in m:
                        return {"check": "model", "pass": True, "message": "Model '%s' is pulled in Ollama" % model_name}
                return {"check": "model", "pass": False, "message": "Model '%s' NOT pulled. Run: ollama pull %s" % (model_name, model_name)}
        except urllib.error.URLError:
            return {"check": "model", "pass": False, "message": "Cannot reach Ollama API to check models"}
        except Exception as e:
            return {"check": "model", "pass": False, "message": "Error checking Ollama models: %s" % str(e)}

    def _check_gguf_model(self, model_path):
        """Check if GGUF file exists on disk."""
        if os.path.exists(model_path):
            size_mb = os.path.getsize(model_path) // (1024 * 1024)
            return {"check": "model", "pass": True, "message": "GGUF file exists (%d MB)" % size_mb}
        return {"check": "model", "pass": False, "message": "GGUF file not found: %s" % model_path}

    def check_ram(self, params):
        """Check if there's enough RAM to load the model."""
        model_size_mb = params.get("model_size_mb", 0)
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                total_ram_bytes = int(result.stdout.strip())
                total_ram_mb = total_ram_bytes // (1024 * 1024)
                # Model needs ~1.5x its size in RAM for inference
                needed_mb = int(model_size_mb * 1.5) if model_size_mb > 0 else 0
                available_mb = total_ram_mb - 2048  # Reserve 2GB for OS
                if needed_mb > 0 and available_mb < needed_mb:
                    return {"check": "ram", "pass": False, "message": "Need %d MB RAM, only %d MB available (total: %d MB)" % (needed_mb, available_mb, total_ram_mb)}
                return {"check": "ram", "pass": True, "message": "RAM OK: %d MB total, ~%d MB available" % (total_ram_mb, available_mb)}
        except Exception:
            pass
        return {"check": "ram", "pass": True, "message": "RAM check skipped (could not detect)"}

    def check_disk_space(self, params):
        """Check if there's enough disk space for model download."""
        model_size_mb = params.get("model_size_mb", 0)
        if model_size_mb == 0:
            return {"check": "disk", "pass": True, "message": "Disk check skipped (model size unknown)"}
        try:
            stat = os.statvfs(os.path.expanduser("~"))
            free_mb = (stat.f_bavail * stat.f_frsize) // (1024 * 1024)
            if free_mb < model_size_mb:
                return {"check": "disk", "pass": False, "message": "Need %d MB disk, only %d MB free" % (model_size_mb, free_mb)}
            return {"check": "disk", "pass": True, "message": "Disk OK: %d MB free (need %d MB)" % (free_mb, model_size_mb)}
        except Exception:
            return {"check": "disk", "pass": True, "message": "Disk check skipped (could not detect)"}

    def check_ollama_running(self, params):
        """Check if Ollama service is running on localhost:11434."""
        try:
            url = "http://localhost:11434/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                return {"check": "ollama", "pass": True, "message": "Ollama is running on localhost:11434"}
        except urllib.error.URLError:
            return {"check": "ollama", "pass": False, "message": "Ollama NOT running. Start it with: ollama serve"}
        except Exception as e:
            return {"check": "ollama", "pass": False, "message": "Cannot reach Ollama: %s" % str(e)}

    def format_result(self, results):
        """Format results into a human-readable summary string."""
        lines = []
        all_pass = True
        for r in results:
            status = "PASS" if r["pass"] else "FAIL"
            if not r["pass"]:
                all_pass = False
            lines.append("[%s] %s: %s" % (status, r["check"], r["message"]))
        header = "=== PRE-FLIGHT CHECK: %s ===" % ("ALL PASS" if all_pass else "ISSUES FOUND")
        return header + "\n" + "\n".join(lines)
