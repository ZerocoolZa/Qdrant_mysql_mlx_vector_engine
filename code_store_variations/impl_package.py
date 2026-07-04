"""VBStyle domain implementation: package.

Package lifecycle: build, fetch, install, resolve, checksum, sign.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import hashlib
import os
import hmac
import base64
import json
import time


class DomPackage:
    """Package domain: build, dependency resolution, install, signing."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "build": self.build,
            "checksum": self.checksum,
            "depend": self.depend,
            "fetch": self.fetch,
            "info": self.info,
            "install": self.install,
            "resolve": self.resolve,
            "sign": self.sign,
            "uninstall": self.uninstall,
            "update": self.update,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def build(self, params=None):
        params = params or {}
        try:
            name = params.get("name") or "package"
            version = params.get("version") or "0.1.0"
            files = params.get("files") or []
            manifest = {"name": name, "version": version, "files": files, "built_at": time.time()}
            self.state["catalog"].append(manifest)
            result = {"domain": "package", "method": "build", "data": {"manifest": manifest, "ok": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BUILD_ERROR", str(e), 0))

    def checksum(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            algo = (params.get("algorithm") or "sha256").lower()
            if path and os.path.isfile(path):
                h = hashlib.new(algo)
                with open(path, "rb") as fh:
                    for chunk in iter(lambda: fh.read(65536), b""):
                        h.update(chunk)
                digest = h.hexdigest()
            else:
                data = (params.get("data") or "").encode("utf-8")
                digest = hashlib.new(algo, data).hexdigest()
            result = {"domain": "package", "method": "checksum", "data": {"algorithm": algo, "checksum": digest}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECKSUM_ERROR", str(e), 0))

    def depend(self, params=None):
        params = params or {}
        try:
            graph = params.get("graph") or {}
            visited = set()
            ordered = []

            def visit(node):
                if node in visited:
                    return
                visited.add(node)
                for dep in graph.get(node, []):
                    visit(dep)
                ordered.append(node)

            for node in graph:
                visit(node)
            result = {"domain": "package", "method": "depend", "data": {"order": ordered, "count": len(ordered)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DEPEND_ERROR", str(e), 0))

    def fetch(self, params=None):
        params = params or {}
        try:
            name = params.get("name") or ""
            source = params.get("source") or ""
            registry = self.state.setdefault("config", {}).setdefault("registry", {})
            record = {"name": name, "source": source, "fetched_at": time.time()}
            registry[name] = record
            result = {"domain": "package", "method": "fetch", "data": {"name": name, "fetched": True, "record": record}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FETCH_ERROR", str(e), 0))

    def info(self, params=None):
        params = params or {}
        try:
            name = params.get("name") or ""
            registry = self.state.setdefault("config", {}).setdefault("registry", {})
            record = registry.get(name)
            result = {"domain": "package", "method": "info", "data": {"name": name, "info": record, "found": record is not None}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INFO_ERROR", str(e), 0))

    def install(self, params=None):
        params = params or {}
        try:
            name = params.get("name") or ""
            version = params.get("version") or "latest"
            installed = self.state.setdefault("config", {}).setdefault("installed", {})
            installed[name] = {"version": version, "installed_at": time.time()}
            result = {"domain": "package", "method": "install", "data": {"name": name, "version": version, "installed": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INSTALL_ERROR", str(e), 0))

    def resolve(self, params=None):
        params = params or {}
        try:
            requirements = params.get("requirements") or []
            graph = params.get("graph") or {}
            resolved = []
            missing = []
            visited = set()

            def visit(node):
                if node in visited:
                    return
                visited.add(node)
                if node not in graph and node not in requirements:
                    missing.append(node)
                    return
                for dep in graph.get(node, []):
                    visit(dep)
                resolved.append(node)

            for req in requirements:
                visit(req)
            result = {"domain": "package", "method": "resolve", "data": {"resolved": resolved, "missing": missing, "ok": len(missing) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RESOLVE_ERROR", str(e), 0))

    def sign(self, params=None):
        params = params or {}
        try:
            payload = (params.get("payload") or "").encode("utf-8")
            key = (params.get("key") or "package-key").encode("utf-8")
            mac = hmac.new(key, payload, hashlib.sha256).hexdigest()
            signature = base64.b64encode(mac.encode()).decode()
            result = {"domain": "package", "method": "sign", "data": {"signature": signature, "algorithm": "HMAC-SHA256"}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SIGN_ERROR", str(e), 0))

    def uninstall(self, params=None):
        params = params or {}
        try:
            name = params.get("name") or ""
            installed = self.state.setdefault("config", {}).setdefault("installed", {})
            existed = name in installed
            if existed:
                del installed[name]
            result = {"domain": "package", "method": "uninstall", "data": {"name": name, "uninstalled": existed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UNINSTALL_ERROR", str(e), 0))

    def update(self, params=None):
        params = params or {}
        try:
            name = params.get("name") or ""
            version = params.get("version") or "latest"
            installed = self.state.setdefault("config", {}).setdefault("installed", {})
            if name not in installed:
                result = {"domain": "package", "method": "update", "data": {"name": name, "updated": False, "reason": "not_installed"}}
                return (1, result, None)
            installed[name] = {"version": version, "updated_at": time.time()}
            result = {"domain": "package", "method": "update", "data": {"name": name, "version": version, "updated": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UPDATE_ERROR", str(e), 0))
