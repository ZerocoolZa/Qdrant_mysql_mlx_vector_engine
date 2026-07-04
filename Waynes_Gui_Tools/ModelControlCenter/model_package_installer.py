#!/usr/bin/env python3
# [@GHOST]{[@file<model_package_installer.py>][@domain<ModelControlCenter>][@role<installer>][@auth<cascade>][@date<2026-07-03>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<installer>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{ModelPackageInstaller — checks, installs, and uninstalls Python packages required by each model framework (CoreML, MLX, PyTorch, ONNX, etc.).}

import subprocess
import sys

from config import PACKAGE_CONFIG


class ModelPackageInstaller:
    """Manages framework-specific Python packages for model files."""

    def __init__(self):
        self.framework_packages = PACKAGE_CONFIG["framework_packages"]
        self.check_commands = PACKAGE_CONFIG["package_check_commands"]
        self.pip_cmd = PACKAGE_CONFIG["pip_command"]
        self.pip_install_flags = PACKAGE_CONFIG["pip_install_flags"]
        self.pip_uninstall_flags = PACKAGE_CONFIG["pip_uninstall_flags"]

    def get_packages_for_framework(self, framework):
        """Return list of pip packages required by a framework."""
        return self.framework_packages.get(framework, [])

    def get_packages_for_model(self, model_dict):
        """Return packages needed for a model dict (uses framework field if available)."""
        framework = model_dict.get("framework")
        if framework:
            return self.get_packages_for_framework(framework)
        ext = model_dict.get("file_type", "")
        from config import IDENTIFIER_CONFIG
        ext_map = IDENTIFIER_CONFIG["extension_to_framework"]
        framework = ext_map.get(ext, "Unknown")
        return self.get_packages_for_framework(framework)

    def check_package(self, package_name):
        """Check if a single package is importable. Returns (installed, import_name)."""
        import_cmd = self.check_commands.get(package_name)
        if not import_cmd:
            return False, None
        script = "import importlib; importlib.import_module('%s')" % import_cmd.replace("import ", "")
        try:
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                timeout=10,
            )
            return proc.returncode == 0, import_cmd
        except (subprocess.TimeoutExpired, OSError):
            return False, import_cmd

    def check_framework_packages(self, framework):
        """Check all packages for a framework. Returns summary dict."""
        packages = self.get_packages_for_framework(framework)
        installed = []
        missing = []
        for pkg in packages:
            ok, _ = self.check_package(pkg)
            if ok:
                installed.append(pkg)
            else:
                missing.append(pkg)
        return {
            "framework": framework,
            "packages": packages,
            "installed": installed,
            "missing": missing,
            "all_installed": len(missing) == 0,
        }

    def check_model_packages(self, model_dict):
        """Check packages for a specific model dict."""
        framework = model_dict.get("framework", "Unknown")
        return self.check_framework_packages(framework)

    def install_package(self, package_name):
        """Install a single pip package. Returns (success, message)."""
        cmd = [self.pip_cmd] + self.pip_install_flags + [package_name]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                return True, "Installed %s" % package_name
            return False, "Failed to install %s: %s" % (package_name, result.stderr.strip()[:200])
        except subprocess.TimeoutExpired:
            return False, "Timeout installing %s" % package_name
        except OSError as e:
            return False, "Error: %s" % str(e)

    def uninstall_package(self, package_name):
        """Uninstall a single pip package. Returns (success, message)."""
        cmd = [self.pip_cmd] + self.pip_uninstall_flags + [package_name]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                return True, "Uninstalled %s" % package_name
            return False, "Failed to uninstall %s: %s" % (package_name, result.stderr.strip()[:200])
        except subprocess.TimeoutExpired:
            return False, "Timeout uninstalling %s" % package_name
        except OSError as e:
            return False, "Error: %s" % str(e)

    def install_framework_packages(self, framework):
        """Install all packages for a framework. Returns (success_count, failure_count, messages)."""
        packages = self.get_packages_for_framework(framework)
        success_count = 0
        failure_count = 0
        messages = []
        for pkg in packages:
            ok, msg = self.install_package(pkg)
            messages.append(msg)
            if ok:
                success_count += 1
            else:
                failure_count += 1
        return success_count, failure_count, messages

    def uninstall_framework_packages(self, framework):
        """Uninstall all packages for a framework. Returns (success_count, failure_count, messages)."""
        packages = self.get_packages_for_framework(framework)
        success_count = 0
        failure_count = 0
        messages = []
        for pkg in packages:
            ok, msg = self.uninstall_package(pkg)
            messages.append(msg)
            if ok:
                success_count += 1
            else:
                failure_count += 1
        return success_count, failure_count, messages

    def install_model_packages(self, model_dict):
        """Install all packages needed for a model. Returns (success_count, failure_count, messages)."""
        framework = model_dict.get("framework", "Unknown")
        return self.install_framework_packages(framework)

    def get_all_frameworks(self):
        """Return all frameworks that have package mappings."""
        return sorted(self.framework_packages.keys())

    def get_status_summary(self):
        """Check all framework packages and return a summary for display."""
        summary = []
        for fw in self.get_all_frameworks():
            check = self.check_framework_packages(fw)
            summary.append(check)
        return summary
