import os
import shutil
import glob as _glob
import tempfile
import stat as _stat
import time


class DomFileops:
    """Filesystem operations domain: read, write, move, stat, walk, glob."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handler = getattr(self, command, None)
        if command == "import":
            handler = None
        if handler is None or command in ("Run",):
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def append(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            data = params.get("data", "")
            if not path:
                return (0, None, ("APPEND_ERROR", "missing path", 0))
            mode = params.get("mode", "a")
            enc = params.get("encoding", "utf-8")
            with open(path, mode, encoding=enc) as fh:
                fh.write(data)
            size = os.path.getsize(path)
            result = {"domain": "fileops", "method": "append", "data": {"path": path, "size": size}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("APPEND_ERROR", str(e), 0))

    def chmod(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path:
                return (0, None, ("CHMOD_ERROR", "missing path", 0))
            mode = params.get("mode")
            if isinstance(mode, str):
                mode = int(mode, 8)
            if mode is None:
                return (0, None, ("CHMOD_ERROR", "missing mode", 0))
            os.chmod(path, mode)
            result = {"domain": "fileops", "method": "chmod", "data": {"path": path, "mode": oct(mode)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHMOD_ERROR", str(e), 0))

    def copy(self, params=None):
        params = params or {}
        try:
            src = params.get("src") or params.get("source")
            dst = params.get("dst") or params.get("dest") or params.get("destination")
            if not src or not dst:
                return (0, None, ("COPY_ERROR", "missing src/dst", 0))
            if params.get("recursive"):
                shutil.copytree(src, dst, dirs_exist_ok=params.get("dirs_exist_ok", True))
            else:
                shutil.copy2(src, dst)
            result = {"domain": "fileops", "method": "copy", "data": {"src": src, "dst": dst}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COPY_ERROR", str(e), 0))

    def delete(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path:
                return (0, None, ("DELETE_ERROR", "missing path", 0))
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.exists(path) or os.path.islink(path):
                os.remove(path)
            result = {"domain": "fileops", "method": "delete", "data": {"path": path, "deleted": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DELETE_ERROR", str(e), 0))

    def exists(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path:
                return (0, None, ("EXISTS_ERROR", "missing path", 0))
            result = {"domain": "fileops", "method": "exists", "data": {"path": path, "exists": os.path.exists(path)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXISTS_ERROR", str(e), 0))

    def glob(self, params=None):
        params = params or {}
        try:
            pattern = params.get("pattern") or params.get("path")
            if not pattern:
                return (0, None, ("GLOB_ERROR", "missing pattern", 0))
            recursive = params.get("recursive", False)
            matches = sorted(_glob.glob(pattern, recursive=recursive))
            result = {"domain": "fileops", "method": "glob", "data": {"pattern": pattern, "matches": matches, "count": len(matches)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GLOB_ERROR", str(e), 0))

    def join(self, params=None):
        params = params or {}
        try:
            parts = params.get("parts") or []
            if isinstance(parts, str):
                parts = [parts]
            if not parts:
                return (0, None, ("JOIN_ERROR", "missing parts", 0))
            joined = os.path.join(*parts)
            result = {"domain": "fileops", "method": "join", "data": {"parts": parts, "joined": joined}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("JOIN_ERROR", str(e), 0))

    def move(self, params=None):
        params = params or {}
        try:
            src = params.get("src") or params.get("source")
            dst = params.get("dst") or params.get("dest") or params.get("destination")
            if not src or not dst:
                return (0, None, ("MOVE_ERROR", "missing src/dst", 0))
            shutil.move(src, dst)
            result = {"domain": "fileops", "method": "move", "data": {"src": src, "dst": dst}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MOVE_ERROR", str(e), 0))

    def read(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path:
                return (0, None, ("READ_ERROR", "missing path", 0))
            enc = params.get("encoding", "utf-8")
            binary = params.get("binary", False)
            if binary:
                with open(path, "rb") as fh:
                    content = fh.read()
                if isinstance(content, bytes):
                    content = content.decode(enc, errors="replace")
            else:
                with open(path, "r", encoding=enc) as fh:
                    content = fh.read()
            result = {"domain": "fileops", "method": "read", "data": {"path": path, "content": content, "size": len(content)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("READ_ERROR", str(e), 0))

    def rename(self, params=None):
        params = params or {}
        try:
            src = params.get("src") or params.get("old")
            dst = params.get("dst") or params.get("new")
            if not src or not dst:
                return (0, None, ("RENAME_ERROR", "missing src/dst", 0))
            os.rename(src, dst)
            result = {"domain": "fileops", "method": "rename", "data": {"src": src, "dst": dst}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RENAME_ERROR", str(e), 0))

    def split(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path:
                return (0, None, ("SPLIT_ERROR", "missing path", 0))
            head, tail = os.path.split(path)
            result = {"domain": "fileops", "method": "split", "data": {"path": path, "head": head, "tail": tail, "ext": os.path.splitext(tail)[1]}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SPLIT_ERROR", str(e), 0))

    def stat(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path:
                return (0, None, ("STAT_ERROR", "missing path", 0))
            st = os.stat(path)
            info = {
                "size": st.st_size,
                "mode": oct(st.st_mode & 0o777),
                "is_dir": _stat.S_ISDIR(st.st_mode),
                "is_file": _stat.S_ISREG(st.st_mode),
                "mtime": st.st_mtime,
                "ctime": st.st_ctime,
                "atime": st.st_atime,
            }
            result = {"domain": "fileops", "method": "stat", "data": {"path": path, "info": info}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STAT_ERROR", str(e), 0))

    def temp(self, params=None):
        params = params or {}
        try:
            suffix = params.get("suffix", "")
            prefix = params.get("prefix", "tmp")
            directory = params.get("dir")
            if params.get("dir_obj"):
                d = tempfile.mkdtemp(prefix=prefix, suffix=suffix, dir=directory)
                result = {"domain": "fileops", "method": "temp", "data": {"path": d, "is_dir": True}}
            else:
                fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=directory)
                os.close(fd)
                result = {"domain": "fileops", "method": "temp", "data": {"path": path, "is_dir": False}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TEMP_ERROR", str(e), 0))

    def touch(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path:
                return (0, None, ("TOUCH_ERROR", "missing path", 0))
            if os.path.exists(path):
                os.utime(path, None)
            else:
                with open(path, "a", encoding="utf-8"):
                    pass
            result = {"domain": "fileops", "method": "touch", "data": {"path": path, "touched": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TOUCH_ERROR", str(e), 0))

    def walk(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            if not path:
                return (0, None, ("WALK_ERROR", "missing path", 0))
            files = []
            dirs = []
            for root, dirnames, filenames in os.walk(path):
                for d in dirnames:
                    dirs.append(os.path.join(root, d))
                for f in filenames:
                    files.append(os.path.join(root, f))
            result = {"domain": "fileops", "method": "walk", "data": {"path": path, "files": files, "dirs": dirs, "file_count": len(files), "dir_count": len(dirs)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WALK_ERROR", str(e), 0))

    def write(self, params=None):
        params = params or {}
        try:
            path = params.get("path")
            data = params.get("data", "")
            if not path:
                return (0, None, ("WRITE_ERROR", "missing path", 0))
            enc = params.get("encoding", "utf-8")
            mode = params.get("mode", "w")
            with open(path, mode, encoding=enc) as fh:
                fh.write(data)
            result = {"domain": "fileops", "method": "write", "data": {"path": path, "size": os.path.getsize(path)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WRITE_ERROR", str(e), 0))
