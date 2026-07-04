import os
import shutil
import time


class DomFolder:
    """Folder operations: create, copy, move, rename, delete, walk, tree, size, archive, clean, compare, watch."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "watched": {},
        }
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "archive": self.archive,
            "clean": self.clean,
            "compare": self.compare,
            "copy": self.copy,
            "create": self.create,
            "delete": self.delete,
            "move": self.move,
            "rename": self.rename,
            "size": self.size,
            "tree": self.tree,
            "walk": self.walk,
            "watch": self.watch,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def create(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path:
                return (0, None, ("MISSING_PATH", "path required", 0))
            os.makedirs(path, exist_ok=True)
            result = {"domain": "folder", "method": "create", "data": {"path": path, "created": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_ERROR", str(e), 0))

    def copy(self, params=None):
        params = params or {}
        try:
            src = params.get("source")
            dst = params.get("destination")
            if not src or not dst:
                return (0, None, ("MISSING_PATHS", "source and destination required", 0))
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            result = {"domain": "folder", "method": "copy", "data": {"source": src, "destination": dst, "copied": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COPY_ERROR", str(e), 0))

    def move(self, params=None):
        params = params or {}
        try:
            src = params.get("source")
            dst = params.get("destination")
            if not src or not dst:
                return (0, None, ("MISSING_PATHS", "source and destination required", 0))
            shutil.move(src, dst)
            result = {"domain": "folder", "method": "move", "data": {"source": src, "destination": dst, "moved": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MOVE_ERROR", str(e), 0))

    def rename(self, params=None):
        params = params or {}
        try:
            src = params.get("source")
            dst = params.get("destination")
            if not src or not dst:
                return (0, None, ("MISSING_PATHS", "source and destination required", 0))
            os.rename(src, dst)
            result = {"domain": "folder", "method": "rename", "data": {"source": src, "destination": dst, "renamed": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RENAME_ERROR", str(e), 0))

    def delete(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path:
                return (0, None, ("MISSING_PATH", "path required", 0))
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.exists(path):
                os.remove(path)
            else:
                return (0, None, ("NOT_FOUND", f"path not found: {path}", 0))
            result = {"domain": "folder", "method": "delete", "data": {"path": path, "deleted": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DELETE_ERROR", str(e), 0))

    def walk(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path or not os.path.isdir(path):
                return (0, None, ("INVALID_PATH", f"not a directory: {path}", 0))
            files = []
            for root, dirs, names in os.walk(path):
                for name in names:
                    files.append(os.path.join(root, name))
            result = {"domain": "folder", "method": "walk", "data": {"path": path, "files": files, "count": len(files)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WALK_ERROR", str(e), 0))

    def tree(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path or not os.path.isdir(path):
                return (0, None, ("INVALID_PATH", f"not a directory: {path}", 0))
            max_depth = int(params.get("max_depth", 3))
            entries = []

            def _walk(p, depth):
                if depth > max_depth:
                    return
                try:
                    for name in sorted(os.listdir(p)):
                        full = os.path.join(p, name)
                        entries.append({"path": full, "depth": depth, "is_dir": os.path.isdir(full)})
                        if os.path.isdir(full):
                            _walk(full, depth + 1)
                except OSError:
                    pass

            _walk(path, 0)
            result = {"domain": "folder", "method": "tree", "data": {"path": path, "entries": entries}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TREE_ERROR", str(e), 0))

    def size(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path or not os.path.exists(path):
                return (0, None, ("INVALID_PATH", f"not found: {path}", 0))
            if os.path.isfile(path):
                total = os.path.getsize(path)
            else:
                total = 0
                for root, dirs, names in os.walk(path):
                    for name in names:
                        try:
                            total += os.path.getsize(os.path.join(root, name))
                        except OSError:
                            pass
            result = {"domain": "folder", "method": "size", "data": {"path": path, "bytes": total}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SIZE_ERROR", str(e), 0))

    def archive(self, params=None):
        params = params or {}
        try:
            src = params.get("source")
            dst = params.get("destination")
            if not src or not dst:
                return (0, None, ("MISSING_PATHS", "source and destination required", 0))
            if not os.path.isdir(src):
                return (0, None, ("INVALID_PATH", f"not a directory: {src}", 0))
            archive_path = shutil.make_archive(dst, params.get("format", "zip"), src)
            result = {"domain": "folder", "method": "archive", "data": {"source": src, "archive": archive_path}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ARCHIVE_ERROR", str(e), 0))

    def clean(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path or not os.path.isdir(path):
                return (0, None, ("INVALID_PATH", f"not a directory: {path}", 0))
            pattern = params.get("pattern")
            removed = 0
            for root, dirs, names in os.walk(path):
                for name in names:
                    if pattern is None or pattern in name:
                        try:
                            os.remove(os.path.join(root, name))
                            removed += 1
                        except OSError:
                            pass
            result = {"domain": "folder", "method": "clean", "data": {"path": path, "removed": removed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLEAN_ERROR", str(e), 0))

    def compare(self, params=None):
        params = params or {}
        try:
            a = params.get("path_a")
            b = params.get("path_b")
            if not a or not b:
                return (0, None, ("MISSING_PATHS", "path_a and path_b required", 0))
            files_a = set()
            files_b = set()
            for base, target in ((a, files_a), (b, files_b)):
                if os.path.isdir(base):
                    for root, dirs, names in os.walk(base):
                        for name in names:
                            rel = os.path.relpath(os.path.join(root, name), base)
                            target.add(rel)
            only_a = sorted(files_a - files_b)
            only_b = sorted(files_b - files_a)
            common = sorted(files_a & files_b)
            result = {"domain": "folder", "method": "compare", "data": {"only_a": only_a, "only_b": only_b, "common": common}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPARE_ERROR", str(e), 0))

    def watch(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path or not os.path.isdir(path):
                return (0, None, ("INVALID_PATH", f"not a directory: {path}", 0))
            snapshot = {}
            for root, dirs, names in os.walk(path):
                for name in names:
                    full = os.path.join(root, name)
                    try:
                        snapshot[full] = (os.path.getsize(full), os.path.getmtime(full))
                    except OSError:
                        pass
            previous = self.state["watched"].get(path, {})
            changed = []
            for full, info in snapshot.items():
                if previous.get(full) != info:
                    changed.append(full)
            self.state["watched"][path] = snapshot
            result = {"domain": "folder", "method": "watch", "data": {"path": path, "changed": changed, "count": len(snapshot)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WATCH_ERROR", str(e), 0))
