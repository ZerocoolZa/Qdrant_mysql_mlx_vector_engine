#!/usr/bin/env python3
# [@GHOST]{[@file<hardware_detector.py>][@domain<ModelControlCenter>][@role<hardware>][@auth<cascade>][@date<2026-07-03>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<hardware>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{HardwareDetector — detects system hardware: RAM, disk space, CPU cores, GPU/Neural Engine. Provides can_fit and can_run checks for model files.}

import os
import shutil
import subprocess
import platform

from config import HARDWARE_CONFIG


class HardwareDetector:
    """Detects system hardware and checks if models can fit in available resources."""

    def __init__(self):
        self.ram_safety_margin_mb = HARDWARE_CONFIG["ram_safety_margin_mb"]
        self.disk_safety_margin_mb = HARDWARE_CONFIG["disk_safety_margin_mb"]
        self.model_ram_multiplier = HARDWARE_CONFIG["model_ram_multiplier"]
        self.check_gpu = HARDWARE_CONFIG["check_gpu"]
        self.check_neural_engine = HARDWARE_CONFIG["check_neural_engine"]

    def detect_all(self):
        """Detect all hardware resources. Returns full system info dict."""
        return {
            "platform": platform.system(),
            "platform_version": platform.mac_ver()[0] if platform.system() == "Darwin" else platform.version(),
            "machine": platform.machine(),
            "cpu_cores": self.get_cpu_cores(),
            "cpu_brand": self.get_cpu_brand(),
            "ram_total_mb": self.get_ram_total_mb(),
            "ram_available_mb": self.get_ram_available_mb(),
            "disk_total_mb": self.get_disk_total_mb(),
            "disk_free_mb": self.get_disk_free_mb(),
            "gpu": self.get_gpu_info() if self.check_gpu else None,
            "neural_engine": self.get_neural_engine_info() if self.check_neural_engine else None,
            "metal_supported": self.is_metal_supported() if self.check_gpu else False,
        }

    def get_cpu_cores(self):
        """Return number of CPU cores."""
        try:
            return os.cpu_count() or 0
        except OSError:
            return 0

    def get_cpu_brand(self):
        """Return CPU brand string on macOS."""
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
        return "Unknown"

    def get_ram_total_mb(self):
        """Return total system RAM in MB."""
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                bytes_val = int(result.stdout.strip())
                return bytes_val // (1024 * 1024)
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
        return 0

    def get_ram_available_mb(self):
        """Return available RAM in MB (total minus used)."""
        try:
            result = subprocess.run(
                ["vm_stat"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                page_size = 4096
                for line in lines:
                    if "page size of" in line:
                        parts = line.split()
                        if len(parts) >= 8:
                            page_size = int(parts[7])
                        break
                free_pages = 0
                for line in lines:
                    if "free" in line.lower() and ":" in line:
                        val = line.split(":")[1].strip().rstrip(".")
                        free_pages += int(val)
                    elif "inactive" in line.lower() and ":" in line:
                        val = line.split(":")[1].strip().rstrip(".")
                        free_pages += int(val)
                return (free_pages * page_size) // (1024 * 1024)
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
        total = self.get_ram_total_mb()
        return total // 2 if total > 0 else 0

    def get_disk_total_mb(self, path=None):
        """Return total disk space in MB for a given path (default: model base dir)."""
        check_path = path or HARDWARE_CONFIG.get("disk_check_path", os.path.expanduser("~"))
        try:
            usage = shutil.disk_usage(check_path)
            return usage.total // (1024 * 1024)
        except OSError:
            return 0

    def get_disk_free_mb(self, path=None):
        """Return free disk space in MB for a given path."""
        check_path = path or HARDWARE_CONFIG.get("disk_check_path", os.path.expanduser("~"))
        try:
            usage = shutil.disk_usage(check_path)
            return usage.free // (1024 * 1024)
        except OSError:
            return 0

    def get_gpu_info(self):
        """Return GPU info on macOS via system_profiler."""
        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                displays = data.get("SPDisplaysDataType", [])
                if displays:
                    gpu = displays[0]
                    return {
                        "name": gpu.get("sppci_model", "Unknown"),
                        "vendor": gpu.get("sppci_vendor", "Unknown"),
                        "metal_support": gpu.get("spdisplays_metal", "Unknown"),
                        "vram_mb": gpu.get("spdisplays_vram", "Unknown"),
                    }
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
        return None

    def get_neural_engine_info(self):
        """Return Apple Neural Engine info on macOS."""
        try:
            result = subprocess.run(
                ["system_profiler", "SPiBridgeDataType", "-json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                bridge = data.get("SPiBridgeDataType", [])
                if bridge:
                    info = bridge[0]
                    return {
                        "name": "Apple Neural Engine",
                        "chip": info.get("sppci_model", "Unknown"),
                        "available": True,
                    }
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
        return {"name": "Apple Neural Engine", "available": False}

    def is_metal_supported(self):
        """Check if Metal GPU framework is available."""
        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                displays = data.get("SPDisplaysDataType", [])
                for d in displays:
                    metal = d.get("spdisplays_metal", "")
                    if metal and metal != "Unknown":
                        return True
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
        return False

    def can_download(self, model_size_mb, path=None):
        """Check if there's enough disk space to download a model."""
        free = self.get_disk_free_mb(path)
        needed = model_size_mb + self.disk_safety_margin_mb
        return {
            "can_download": free >= needed,
            "free_mb": free,
            "needed_mb": needed,
            "model_size_mb": model_size_mb,
            "safety_margin_mb": self.disk_safety_margin_mb,
            "shortfall_mb": max(0, needed - free),
        }

    def can_run(self, model_size_mb):
        """Check if there's enough RAM to run a model (model size * multiplier)."""
        available = self.get_ram_available_mb()
        needed = int(model_size_mb * self.model_ram_multiplier)
        return {
            "can_run": available >= needed,
            "available_ram_mb": available,
            "needed_ram_mb": needed,
            "model_size_mb": model_size_mb,
            "ram_multiplier": self.model_ram_multiplier,
            "shortfall_mb": max(0, needed - available),
        }

    def check_model(self, model_dict, path=None):
        """Full hardware check for a model dict. Returns combined download + run assessment."""
        size_mb = model_dict.get("size_mb", 0)
        download_check = self.can_download(size_mb, path)
        run_check = self.can_run(size_mb)
        return {
            "model_name": model_dict.get("name", "Unknown"),
            "model_size_mb": size_mb,
            "can_download": download_check,
            "can_run": run_check,
            "overall_ok": download_check["can_download"] and run_check["can_run"],
            "warnings": self.generate_warnings(download_check, run_check, model_dict),
        }

    def generate_warnings(self, download_check, run_check, model_dict):
        """Generate human-readable warning messages."""
        warnings = []
        if not download_check["can_download"]:
            warnings.append(
                "Not enough disk space: need %d MB, have %d MB (short by %d MB)" % (
                    download_check["needed_mb"], download_check["free_mb"], download_check["shortfall_mb"]
                )
            )
        if not run_check["can_run"]:
            warnings.append(
                "Not enough RAM to run: need %d MB, have %d MB (short by %d MB)" % (
                    run_check["needed_ram_mb"], run_check["available_ram_mb"], run_check["shortfall_mb"]
                )
            )
        size_mb = model_dict.get("size_mb", 0)
        if size_mb > 5000 and run_check["available_ram_mb"] < 8000:
            warnings.append("Large model (%d MB) with limited RAM — may be slow or unstable" % size_mb)
        if size_mb > 20000:
            warnings.append("Very large model (%d MB) — ensure adequate cooling and power" % size_mb)
        return warnings

    def get_summary(self):
        """Return a concise hardware summary for display in GUI."""
        info = self.detect_all()
        return {
            "cpu": info["cpu_brand"],
            "cores": info["cpu_cores"],
            "ram_total_mb": info["ram_total_mb"],
            "ram_available_mb": info["ram_available_mb"],
            "disk_free_mb": info["disk_free_mb"],
            "disk_total_mb": info["disk_total_mb"],
            "gpu": info["gpu"]["name"] if info["gpu"] else "None",
            "metal": info["metal_supported"],
            "neural_engine": info["neural_engine"]["available"] if info["neural_engine"] else False,
        }
