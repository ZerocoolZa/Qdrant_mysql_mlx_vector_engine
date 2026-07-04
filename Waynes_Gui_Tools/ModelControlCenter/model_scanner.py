#!/usr/bin/env python3
# [@GHOST]{[@file<model_scanner.py>][@domain<ModelControlCenter>][@role<scanner>][@auth<cascade>][@date<2026-07-03>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<scanner>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{ModelScanner — discovers model files on disk by walking configured directories. Filters by extension, min size, and depth. Returns model dicts ready for registry.}

import os

from config import SCANNER_CONFIG
from model_identifier import ModelIdentifier


class ModelScanner:
    """Scans local filesystem for model files using config-driven settings."""

    def __init__(self, existing_paths=None, identify=True):
        self.directories = SCANNER_CONFIG["directories"]
        self.extensions = SCANNER_CONFIG["extensions"]
        self.max_depth = SCANNER_CONFIG["max_depth"]
        self.min_size_mb = SCANNER_CONFIG["min_file_size_mb"]
        self.skip_hidden = SCANNER_CONFIG["skip_hidden"]
        self.existing_paths = set()
        if existing_paths:
            for p in existing_paths:
                self.existing_paths.add(os.path.normpath(p))
        self.identify_enabled = identify
        self.identifier = ModelIdentifier() if identify else None

    def scan(self):
        """Walk all configured directories and return discovered model dicts."""
        discovered = []
        seen_paths = set()

        for scan_dir in self.directories:
            if not os.path.isdir(scan_dir):
                continue
            for found in self.walk_dir(scan_dir, depth=0):
                norm = os.path.normpath(found["local_path"])
                if norm in seen_paths:
                    continue
                parent = os.path.dirname(norm)
                if any(parent.startswith(ep) for ep in self.existing_paths):
                    continue
                seen_paths.add(norm)
                discovered.append(found)

        return discovered

    def walk_dir(self, directory, depth=0):
        """Recursively scan a directory for model files."""
        if depth > self.max_depth:
            return []
        results = []
        try:
            entries = os.listdir(directory)
        except (PermissionError, OSError):
            return []

        for entry in entries:
            if self.skip_hidden and entry.startswith(".") and depth > 0:
                continue
            full_path = os.path.join(directory, entry)

            if os.path.isdir(full_path):
                results.extend(self.walk_dir(full_path, depth + 1))
                continue

            ext = os.path.splitext(entry)[1].lower()
            if ext not in self.extensions:
                continue

            try:
                file_size = os.path.getsize(full_path)
            except OSError:
                continue

            size_mb = file_size // (1024 * 1024)
            if size_mb < self.min_size_mb:
                continue

            model_id = "scan_%s" % entry.replace(".", "_").replace(" ", "_").lower()
            model_name = os.path.splitext(entry)[0].replace("_", " ").title()
            parent_dir = os.path.dirname(full_path)

            entry_dict = {
                "id": model_id,
                "name": model_name,
                "size_mb": size_mb,
                "description": "Discovered on disk: %s" % full_path,
                "platforms": ["mac"],
                "pip": [],
                "source_url": None,
                "local_path": parent_dir,
                "status": "installed",
                "version": "unknown",
                "category": "Discovered",
                "file_path": full_path,
                "file_type": ext,
            }

            if self.identifier:
                ident = self.identifier.identify(full_path)
                entry_dict["framework"] = ident["framework"]
                entry_dict["format_confirmed"] = ident["format_confirmed"]
                entry_dict["magic_match"] = ident["magic_match"]
                entry_dict["model_metadata"] = ident["metadata"]
                entry_dict["category"] = ident["category"]

            results.append(entry_dict)

        return results

    def get_config_info(self):
        """Return a summary of scanner configuration for display."""
        info = {
            "directories": self.directories,
            "extensions": self.extensions,
            "max_depth": self.max_depth,
            "min_size_mb": self.min_size_mb,
            "skip_hidden": self.skip_hidden,
            "existing_paths_count": len(self.existing_paths),
            "identification_enabled": self.identify_enabled,
        }
        if self.identifier:
            info["supported_frameworks"] = self.identifier.get_supported_frameworks()
        return info
