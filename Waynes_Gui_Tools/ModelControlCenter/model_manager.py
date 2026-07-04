#!/usr/bin/env python3
# [@GHOST]{[@file<model_manager.py>][@domain<ModelControlCenter>][@role<manager>][@auth<cascade>][@date<2026-07-03>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<manager>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{ModelManager — logic layer for install/uninstall/delete/restore models. Handles pip deps, local file management, and JSON persistence.}

import os
import shutil
import subprocess

from config import load_registry, save_registry, MODELS_BASE_DIR
from model_scanner import ModelScanner
from model_tester import ModelTester
from model_package_installer import ModelPackageInstaller
from hardware_detector import HardwareDetector


class ModelManager:
    """Manages model lifecycle: install, uninstall, delete, restore."""

    def __init__(self):
        self.models = load_registry()
        self.base_dir = MODELS_BASE_DIR
        self.tester = ModelTester()
        self.package_installer = ModelPackageInstaller()
        self.hardware = HardwareDetector()

    def list_models(self):
        return self.models

    def get_model(self, model_id):
        for m in self.models:
            if m["id"] == model_id:
                return m
        return None

    def get_categories(self):
        cats = set()
        for m in self.models:
            cats.add(m.get("category", "Other"))
        return sorted(cats)

    def install_model(self, model_id):
        """Install pip dependencies and create local path. Checks hardware first. Returns (success, message)."""
        model = self.get_model(model_id)
        if not model:
            return False, "Model not found: %s" % model_id

        hw_check = self.hardware.check_model(model)
        if not hw_check["can_download"]["can_download"]:
            return False, "Cannot download: %s" % hw_check["warnings"][0]
        if not hw_check["can_run"]["can_run"]:
            return False, "Cannot run: %s" % hw_check["warnings"][0]

        pip_deps = model.get("pip", [])
        if pip_deps:
            for pkg in pip_deps:
                try:
                    subprocess.check_call(
                        ["pip3", "install", "--quiet", pkg],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except subprocess.CalledProcessError:
                    return False, "Failed to install pip package: %s" % pkg

        local_path = model.get("local_path")
        if local_path:
            os.makedirs(local_path, exist_ok=True)

        model["status"] = "installed"
        save_registry(self.models)
        return True, "Installed %s" % model["name"]

    def uninstall_model(self, model_id):
        """Mark model as not installed but keep files on disk."""
        model = self.get_model(model_id)
        if not model:
            return False, "Model not found"
        model["status"] = "not_installed"
        save_registry(self.models)
        return True, "Uninstalled %s" % model["name"]

    def delete_model(self, model_id):
        """Delete model files from disk and mark as deleted."""
        model = self.get_model(model_id)
        if not model:
            return False, "Model not found"

        local_path = model.get("local_path")
        if local_path and os.path.exists(local_path):
            try:
                shutil.rmtree(local_path)
            except OSError:
                return False, "Failed to delete files at %s" % local_path

        model["status"] = "deleted"
        save_registry(self.models)
        return True, "Deleted %s" % model["name"]

    def restore_model(self, model_id):
        """Restore a deleted model back to installed state."""
        model = self.get_model(model_id)
        if not model:
            return False, "Model not found"

        local_path = model.get("local_path")
        if local_path:
            os.makedirs(local_path, exist_ok=True)

        model["status"] = "installed"
        save_registry(self.models)
        return True, "Restored %s" % model["name"]

    def filter_models(self, category="All", search=""):
        """Filter models by category and search term."""
        results = []
        search_lower = search.lower()
        for m in self.models:
            if category != "All" and m.get("category", "Other") != category:
                continue
            if search_lower:
                name = m["name"].lower()
                desc = m["description"].lower()
                cat = m.get("category", "").lower()
                if search_lower not in name and search_lower not in desc and search_lower not in cat:
                    continue
            results.append(m)
        return results

    def scan_models(self):
        """Scan local filesystem for model files using ModelScanner."""
        existing_paths = []
        for m in self.models:
            lp = m.get("local_path")
            if lp:
                existing_paths.append(lp)
        scanner = ModelScanner(existing_paths=existing_paths)
        return scanner.scan()

    def get_scanner_info(self):
        """Return scanner configuration for display."""
        scanner = ModelScanner()
        return scanner.get_config_info()

    def test_model(self, model_id):
        """Run validation tests on a model's file. Returns test result dict."""
        model = self.get_model(model_id)
        if not model:
            return {"overall_pass": False, "tests_failed": ["model_not_found"]}
        file_path = model.get("file_path") or model.get("local_path")
        if not file_path or not os.path.exists(file_path):
            return {"overall_pass": False, "tests_failed": ["file_not_found"]}
        framework = model.get("framework")
        return self.tester.test(file_path, framework=framework)

    def check_model_packages(self, model_id):
        """Check which packages a model needs and which are installed."""
        model = self.get_model(model_id)
        if not model:
            return None
        return self.package_installer.check_model_packages(model)

    def install_model_packages(self, model_id):
        """Install all framework packages for a model. Returns (success, failures, messages)."""
        model = self.get_model(model_id)
        if not model:
            return 0, 0, ["Model not found"]
        return self.package_installer.install_model_packages(model)

    def uninstall_model_packages(self, model_id):
        """Uninstall framework packages for a model. Returns (success, failures, messages)."""
        model = self.get_model(model_id)
        if not model:
            return 0, 0, ["Model not found"]
        framework = model.get("framework", "Unknown")
        return self.package_installer.uninstall_framework_packages(framework)

    def get_package_status_summary(self):
        """Return package status for all frameworks."""
        return self.package_installer.get_status_summary()

    def get_hardware_info(self):
        """Return full hardware detection info."""
        return self.hardware.detect_all()

    def get_hardware_summary(self):
        """Return concise hardware summary for GUI display."""
        return self.hardware.get_summary()

    def check_model_hardware(self, model_id):
        """Check if a model can be downloaded and run on current hardware."""
        model = self.get_model(model_id)
        if not model:
            return None
        return self.hardware.check_model(model)

    def add_discovered(self, discovered_models):
        """Add discovered models to registry, skipping duplicates by id."""
        existing_ids = set(m["id"] for m in self.models)
        added = 0
        for dm in discovered_models:
            if dm["id"] not in existing_ids:
                self.models.append(dm)
                existing_ids.add(dm["id"])
                added += 1
        if added > 0:
            save_registry(self.models)
        return added

    def get_stats(self):
        """Return summary statistics."""
        total = len(self.models)
        installed = sum(1 for m in self.models if m["status"] == "installed")
        not_installed = sum(1 for m in self.models if m["status"] == "not_installed")
        deleted = sum(1 for m in self.models if m["status"] == "deleted")
        total_size = sum(m.get("size_mb", 0) for m in self.models if m["status"] == "installed")
        return {
            "total": total,
            "installed": installed,
            "not_installed": not_installed,
            "deleted": deleted,
            "total_size_mb": total_size,
        }
