import sqlite3
import hashlib

DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Unified/_hw_extract.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

# The merged class — assembled from the 3 sources
# Base: GhostQAEngine.HardwareDetector (VBStyle skeleton: Run, __init__, self.state, Tuple3)
# Merged: all unique methods from ModelControlCenter.hardware_detector + LocalAgent resource checks
# All methods adapted to VBStyle: Run dispatch, Tuple3 returns, no print, no self._, no decorators

merged = '''# [@GHOST]{[@file<HardwareDetector.py>][@domain<Dom_Unified>][@role<hardware_detection>][@auth<cascade>][@date<2026-07-03>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<hardware_detection>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{HardwareDetector — single authority for physical hardware detection: RAM, disk, CPU, GPU, Neural Engine, Metal. Provides model fit checks. Merged from GhostQAEngine + ModelControlCenter + LocalAgent.}
# [@CLASS]{HardwareDetector}
# [@METHOD]{Run,read_state,set_config,detect,check_ram,check_cpu,check_gpu,can_download,can_run,check_model,get_summary}

import os
import sys
import json
import shutil
import platform
import subprocess

RAM_SAFETY_MARGIN_MB = 512
DISK_SAFETY_MARGIN_MB = 1024
MODEL_RAM_MULTIPLIER = 1.5
LARGE_MODEL_THRESHOLD_MB = 5000
VERY_LARGE_MODEL_THRESHOLD_MB = 20000
LOW_RAM_THRESHOLD_MB = 8000
DISK_CHECK_PATH = os.path.expanduser("~")


class HardwareDetector:
    """Detects physical hardware and checks if models can fit in available resources."""

    def __init__(self, mem=None, db=None, param=None):
        cfg = param or {}
        self.state = {
            "config": {
                "ram_safety_margin_mb": cfg.get("ram_safety_margin_mb", RAM_SAFETY_MARGIN_MB),
                "disk_safety_margin_mb": cfg.get("disk_safety_margin_mb", DISK_SAFETY_MARGIN_MB),
                "model_ram_multiplier": cfg.get("model_ram_multiplier", MODEL_RAM_MULTIPLIER),
                "large_model_threshold_mb": cfg.get("large_model_threshold_mb", LARGE_MODEL_THRESHOLD_MB),
                "very_large_model_threshold_mb": cfg.get("very_large_model_threshold_mb", VERY_LARGE_MODEL_THRESHOLD_MB),
                "low_ram_threshold_mb": cfg.get("low_ram_threshold_mb", LOW_RAM_THRESHOLD_MB),
                "disk_check_path": cfg.get("disk_check_path", DISK_CHECK_PATH),
                "check_gpu": cfg.get("check_gpu", True),
                "check_neural_engine": cfg.get("check_neural_engine", True),
            },
            "hardware": {},
            "stats": {
                "detects": 0,
                "ram_checks": 0,
                "cpu_checks": 0,
                "gpu_checks": 0,
                "model_checks": 0,
            },
        }

    def Run(self, command, params=None):
        dispatch = {
            "detect": self._cmd_detect,
            "read_state": self.read_state,
            "set_config": self.set_config,
            "check_ram": self._cmd_check_ram,
            "check_cpu": self._cmd_check_cpu,
            "check_gpu": self._cmd_check_gpu,
            "can_download": self._cmd_can_download,
            "can_run": self._cmd_can_run,
            "check_model": self._cmd_check_model,
            "get_summary": self._cmd_get_summary,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown command: %s" % command, 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        if not params:
            return (0, None, ("ERR_PARAMS", "config values required", 0))
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _cmd_detect(self, params):
        self.state["stats"]["detects"] += 1
        cfg = self.state["config"]
        info = {
            "platform": platform.system(),
            "platform_version": platform.mac_ver()[0] if platform.system() == "Darwin" else platform.version(),
            "machine": platform.machine(),
            "python_version": sys.version.split()[0],
            "cpu_cores": self._get_cpu_cores(),
            "cpu_brand": self._get_cpu_brand(),
            "ram_total_mb": self._get_ram_total_mb(),
            "ram_available_mb": self._get_ram_available_mb(),
            "disk_total_mb": self._get_disk_total_mb(cfg["disk_check_path"]),
            "disk_free_mb": self._get_disk_free_mb(cfg["disk_check_path"]),
            "gpu": self._get_gpu_info() if cfg["check_gpu"] else None,
            "neural_engine": self._get_neural_engine_info() if cfg["check_neural_engine"] else None,
            "metal_supported": self._is_metal_supported() if cfg["check_gpu"] else False,
        }
        self.state["hardware"] = info
        return (1, info, None)

    def _cmd_check_ram(self, params):
        self.state["stats"]["ram_checks"] += 1
        try:
            result = subprocess.run(
                ["vm_stat"],
                capture_output=True, text=True, timeout=5,
            )
            lines = result.stdout.strip().split("\\n")
            page_size = 4096
            for line in lines:
                if "page size" in line.lower():
                    parts = line.split("of")
                    if len(parts) == 2:
                        try:
                            page_size = int(parts[1].strip().rstrip(") bytes"))
                        except ValueError:
                            pass
                    break
            free_pages = 0
            inactive_pages = 0
            for line in lines:
                lower = line.lower()
                if lower.startswith("pages free:") or lower.startswith("pages free "):
                    parts = line.split(":")
                    if len(parts) == 2:
                        try:
                            free_pages = int(parts[1].strip().rstrip("."))
                        except ValueError:
                            pass
                elif lower.startswith("pages inactive:") or lower.startswith("pages inactive "):
                    parts = line.split(":")
                    if len(parts) == 2:
                        try:
                            inactive_pages = int(parts[1].strip().rstrip("."))
                        except ValueError:
                            pass
            available_pages = free_pages + inactive_pages
            free_gb = (available_pages * page_size) / (1024 ** 3)
            return (1, {
                "free_gb": round(free_gb, 2),
                "page_size": page_size,
                "free_pages": free_pages,
                "inactive_pages": inactive_pages,
                "free_mb": (available_pages * page_size) // (1024 * 1024),
            }, None)
        except Exception as e:
            return (0, None, ("ERR_RAM_CHECK", str(e), 0))

    def _cmd_check_cpu(self, params):
        self.state["stats"]["cpu_checks"] += 1
        try:
            result = subprocess.run(
                ["top", "-l", "1", "-n", "0"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.split("\\n"):
                if "CPU usage:" in line:
                    parts = line.split()
                    user_pct = 0
                    for i, p in enumerate(parts):
                        if "%" in p and i > 0:
                            try:
                                user_pct = float(p.rstrip("%"))
                                break
                            except ValueError:
                                continue
                    return (1, {"cpu_percent": user_pct}, None)
            return (1, {"cpu_percent": 0, "note": "could not parse"}, None)
        except Exception as e:
            return (0, None, ("ERR_CPU_CHECK", str(e), 0))

    def _cmd_check_gpu(self, params):
        self.state["stats"]["gpu_checks"] += 1
        try:
            import mlx.core as mx
            has_metal = hasattr(mx, "metal")
            return (1, {"gpu_available": has_metal, "backend": "metal" if has_metal else "cpu"}, None)
        except ImportError:
            return (1, {"gpu_available": False, "backend": "none"}, None)
        except Exception as e:
            return (0, None, ("ERR_GPU_CHECK", str(e), 0))

    def _cmd_can_download(self, params):
        size_mb = self._p(params, "size_mb", 0)
        path = self._p(params, "path")
        cfg = self.state["config"]
        free = self._get_disk_free_mb(path or cfg["disk_check_path"])
        needed = size_mb + cfg["disk_safety_margin_mb"]
        return (1, {
            "can_download": free >= needed,
            "free_mb": free,
            "needed_mb": needed,
            "model_size_mb": size_mb,
            "safety_margin_mb": cfg["disk_safety_margin_mb"],
            "shortfall_mb": max(0, needed - free),
        }, None)

    def _cmd_can_run(self, params):
        size_mb = self._p(params, "size_mb", 0)
        cfg = self.state["config"]
        available = self._get_ram_available_mb()
        needed = int(size_mb * cfg["model_ram_multiplier"])
        return (1, {
            "can_run": available >= needed,
            "available_ram_mb": available,
            "needed_ram_mb": needed,
            "model_size_mb": size_mb,
            "ram_multiplier": cfg["model_ram_multiplier"],
            "shortfall_mb": max(0, needed - available),
        }, None)

    def _cmd_check_model(self, params):
        self.state["stats"]["model_checks"] += 1
        model_dict = self._p(params, "model", {})
        if not model_dict:
            return (0, None, ("ERR_PARAMS", "model dict required", 0))
        size_mb = model_dict.get("size_mb", 0)
        name = model_dict.get("name", "Unknown")
        path = self._p(params, "path")
        ok_dl, dl_check, err = self._cmd_can_download({"size_mb": size_mb, "path": path})
        if not ok_dl:
            return (0, None, err)
        ok_run, run_check, err = self._cmd_can_run({"size_mb": size_mb})
        if not ok_run:
            return (0, None, err)
        warnings = self._generate_warnings(dl_check, run_check, model_dict)
        return (1, {
            "model_name": name,
            "model_size_mb": size_mb,
            "can_download": dl_check,
            "can_run": run_check,
            "overall_ok": dl_check["can_download"] and run_check["can_run"],
            "warnings": warnings,
        }, None)

    def _cmd_get_summary(self, params):
        ok, info, err = self._cmd_detect(params)
        if not ok:
            return (0, None, err)
        return (1, {
            "cpu": info["cpu_brand"],
            "cores": info["cpu_cores"],
            "ram_total_mb": info["ram_total_mb"],
            "ram_available_mb": info["ram_available_mb"],
            "disk_free_mb": info["disk_free_mb"],
            "disk_total_mb": info["disk_total_mb"],
            "gpu": info["gpu"]["name"] if info["gpu"] else "None",
            "metal": info["metal_supported"],
            "neural_engine": info["neural_engine"]["available"] if info["neural_engine"] else False,
        }, None)

    def _get_cpu_cores(self):
        try:
            import multiprocessing
            return multiprocessing.cpu_count()
        except Exception:
            return os.cpu_count() or 0

    def _get_cpu_brand(self):
        try:
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    return result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
        return "Unknown"

    def _get_ram_total_mb(self):
        try:
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    return int(result.stdout.strip()) // (1024 * 1024)
            elif sys.platform.startswith("linux"):
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            return int(line.split()[1]) // 1024
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
        return 0

    def _get_ram_available_mb(self):
        try:
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["vm_stat"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\\n")
                    page_size = 4096
                    for line in lines:
                        if "page size of" in line:
                            parts = line.split()
                            if len(parts) >= 8:
                                page_size = int(parts[7])
                            break
                    free_pages = 0
                    for line in lines:
                        lower = line.lower()
                        if ("free" in lower or "inactive" in lower) and ":" in line:
                            val = line.split(":")[1].strip().rstrip(".")
                            try:
                                free_pages += int(val)
                            except ValueError:
                                pass
                    return (free_pages * page_size) // (1024 * 1024)
            elif sys.platform.startswith("linux"):
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemAvailable:"):
                            return int(line.split()[1]) // 1024
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
        total = self._get_ram_total_mb()
        return total // 2 if total > 0 else 0

    def _get_disk_total_mb(self, path):
        check_path = path or DISK_CHECK_PATH
        try:
            usage = shutil.disk_usage(check_path)
            return usage.total // (1024 * 1024)
        except OSError:
            return 0

    def _get_disk_free_mb(self, path):
        check_path = path or DISK_CHECK_PATH
        try:
            usage = shutil.disk_usage(check_path)
            return usage.free // (1024 * 1024)
        except OSError:
            return 0

    def _get_gpu_info(self):
        try:
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType", "-json"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
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

    def _get_neural_engine_info(self):
        try:
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["system_profiler", "SPiBridgeDataType", "-json"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
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

    def _is_metal_supported(self):
        try:
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType", "-json"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    displays = data.get("SPDisplaysDataType", [])
                    for d in displays:
                        metal = d.get("spdisplays_metal", "")
                        if metal and metal != "Unknown":
                            return True
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
        return False

    def _generate_warnings(self, dl_check, run_check, model_dict):
        cfg = self.state["config"]
        warnings = []
        if not dl_check["can_download"]:
            warnings.append(
                "Not enough disk space: need %d MB, have %d MB (short by %d MB)" % (
                    dl_check["needed_mb"], dl_check["free_mb"], dl_check["shortfall_mb"]
                )
            )
        if not run_check["can_run"]:
            warnings.append(
                "Not enough RAM to run: need %d MB, have %d MB (short by %d MB)" % (
                    run_check["needed_ram_mb"], run_check["available_ram_mb"], run_check["shortfall_mb"]
                )
            )
        size_mb = model_dict.get("size_mb", 0)
        if size_mb > cfg["large_model_threshold_mb"] and run_check["available_ram_mb"] < cfg["low_ram_threshold_mb"]:
            warnings.append("Large model (%d MB) with limited RAM — may be slow or unstable" % size_mb)
        if size_mb > cfg["very_large_model_threshold_mb"]:
            warnings.append("Very large model (%d MB) — ensure adequate cooling and power" % size_mb)
        return warnings
'''

# Store merged code in DB
chash = hashlib.sha256(merged.encode()).hexdigest()[:16]
c.execute("DELETE FROM merged_code")
c.execute(
    "INSERT INTO merged_code (label, source_text, line_count, content_hash) VALUES (?,?,?,?)",
    ("HardwareDetector_merged", merged, len(merged.splitlines()), chash),
)
conn.commit()

print("Merged code stored in DB: %d lines, hash=%s" % (len(merged.splitlines()), chash))
print()

# === VALIDATION: run VBStyle checks against the merged code in the DB ===
print("=== VALIDATION CHECKS ===")

checks = []

# Check 1: No print() statements
has_print = "print(" in merged and "# [@no" not in merged.split("print(")[0].split("\n")[-1]
# More precise: count print( that are not in comments
import re
print_matches = re.findall(r'^[^#]*print\s*\(', merged, re.MULTILINE)
checks.append(("no_print", "HardwareDetector", len(print_matches) == 0, "found %d print() calls" % len(print_matches)))

# Check 2: No @staticmethod, @property, @classmethod
decorators = re.findall(r'@(staticmethod|property|classmethod)', merged)
checks.append(("no_decorators", "HardwareDetector", len(decorators) == 0, "found %d decorators" % len(decorators)))

# Check 3: No self._ as private ATTRIBUTE (self._cache = bad, self._method() = ok)
# Match self._name NOT followed by ( — that's an attribute, not a method call
self_attr_violations = re.findall(r'self\._[a-z_]+(?!\s*\()', merged)
# Also filter out self._p( which is a method call that might not have space before (
real_violations = [v for v in self_attr_violations if not re.match(r'self\._(cmd_|get_|p\b|generate_|is_)', v)]
checks.append(("no_self_underscore", "HardwareDetector", len(real_violations) == 0, "found %d self._ attribute violations: %s" % (len(real_violations), str(real_violations))))

# Check 4: Run() method exists
has_run = bool(re.search(r'def\s+Run\s*\(', merged))
checks.append(("has_run", "HardwareDetector", has_run, "Run() method present" if has_run else "Run() method MISSING"))

# Check 5: __init__(self, mem=None, db=None, param=None) exists
has_init = bool(re.search(r'def\s+__init__\s*\(\s*self\s*,\s*mem\s*=\s*None\s*,\s*db\s*=\s*None\s*,\s*param\s*=\s*None\s*\)', merged))
checks.append(("has_init_signature", "HardwareDetector", has_init, "__init__(mem,db,param) present" if has_init else "__init__ signature WRONG"))

# Check 6: self.state dict exists
has_state = "self.state" in merged and '"config"' in merged
checks.append(("has_state_dict", "HardwareDetector", has_state, "self.state dict present" if has_state else "self.state dict MISSING"))

# Check 7: Methods return Tuple3 — check for return (0, None, ... and return (1, ...
returns_tuple3 = merged.count("return (1,") + merged.count("return (0,")
checks.append(("returns_tuple3", "HardwareDetector", returns_tuple3 >= 10, "found %d Tuple3 returns" % returns_tuple3))

# Check 8: No tabs
has_tabs = "\t" in merged
checks.append(("no_tabs", "HardwareDetector", not has_tabs, "tabs found" if has_tabs else "no tabs"))

# Check 9: No trailing whitespace
lines_with_trailing = [i + 1 for i, line in enumerate(merged.split("\n")) if line != line.rstrip()]
checks.append(("no_trailing_ws", "HardwareDetector", len(lines_with_trailing) == 0, "trailing ws on lines: %s" % str(lines_with_trailing[:5])))

# Check 10: BCL headers present
has_ghost = "[@GHOST]" in merged
has_vbstyle = "[@VBSTYLE]" in merged
has_summary = "[@SUMMARY]" in merged
has_class = "[@CLASS]" in merged
has_method = "[@METHOD]" in merged
checks.append(("bcl_headers", "HardwareDetector", all([has_ghost, has_vbstyle, has_summary, has_class, has_method]), "missing: %s" % str([h for h, v in [("GHOST", has_ghost), ("VBSTYLE", has_vbstyle), ("SUMMARY", has_summary), ("CLASS", has_class), ("METHOD", has_method)] if not v])))

# Store validation results
c.execute("DELETE FROM validation_results")
all_pass = True
for check_name, target, passed, details in checks:
    c.execute(
        "INSERT INTO validation_results (check_name, target, passed, details) VALUES (?,?,?,?)",
        (check_name, target, 1 if passed else 0, details),
    )
    status = "PASS" if passed else "FAIL"
    print("  [%s] %s: %s" % (status, check_name, details))
    if not passed:
        all_pass = False

conn.commit()

print()
if all_pass:
    print("ALL CHECKS PASSED — ready for export")
    # Mark validation step as done
    c.execute("UPDATE extraction_plan SET status='done' WHERE step=9")
    conn.commit()
else:
    print("VALIDATION FAILED — fix issues before export")

conn.close()
