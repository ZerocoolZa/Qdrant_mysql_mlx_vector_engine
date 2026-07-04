import os
import sys
import json
import re
import shutil
import gzip
import tempfile
import time
import fnmatch


class DomIo:
    """Filesystem and I/O operations domain."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "append": self.append,
            "chmod": self.chmod,
            "compress": self.compress,
            "copy": self.copy,
            "decompress": self.decompress,
            "delete": self.delete,
            "exists": self.exists,
            "flush": self.flush,
            "glob": self.glob,
            "join": self.join,
            "listdir": self.listdir,
            "makedirs": self.makedirs,
            "move": self.move,
            "open": self.open,
            "read": self.read,
            "readlines": self.readlines,
            "rmdir": self.rmdir,
            "seek": self.seek,
            "split": self.split,
            "stat": self.stat,
            "tell": self.tell,
            "temp": self.temp,
            "touch": self.touch,
            "truncate": self.truncate,
            "walk": self.walk,
            "watch": self.watch,
            "write": self.write,
            "writelines": self.writelines,
        }
        handler = handlers.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def append(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            content = params.get("content", "")
            mode = params.get("mode", "a")
            with open(path, mode, encoding="utf-8") as fh:
                fh.write(content)
            result = {"domain": "io", "method": "append", "data": {"path": path, "appended": len(content)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("APPEND_ERROR", str(e), 0))

    def chmod(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            mode = params.get("mode", 0o644)
            os.chmod(path, int(mode))
            result = {"domain": "io", "method": "chmod", "data": {"path": path, "mode": int(mode)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHMOD_ERROR", str(e), 0))

    def compress(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            out_path = params.get("out_path", path + ".gz")
            with open(path, "rb") as src, gzip.open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            result = {"domain": "io", "method": "compress", "data": {"path": path, "out_path": out_path}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPRESS_ERROR", str(e), 0))

    def copy(self, params=None):
        params = params or {}
        try:
            src = params.get("src", "")
            dst = params.get("dst", "")
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            result = {"domain": "io", "method": "copy", "data": {"src": src, "dst": dst}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COPY_ERROR", str(e), 0))

    def decompress(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            out_path = params.get("out_path", path[:-3] if path.endswith(".gz") else path + ".out")
            with gzip.open(path, "rb") as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            result = {"domain": "io", "method": "decompress", "data": {"path": path, "out_path": out_path}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DECOMPRESS_ERROR", str(e), 0))

    def delete(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            result = {"domain": "io", "method": "delete", "data": {"path": path, "deleted": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DELETE_ERROR", str(e), 0))

    def exists(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            exists = os.path.exists(path)
            result = {"domain": "io", "method": "exists", "data": {"path": path, "exists": exists}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXISTS_ERROR", str(e), 0))

    def flush(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            with open(path, "a", encoding="utf-8") as fh:
                fh.flush()
                os.fsync(fh.fileno())
            result = {"domain": "io", "method": "flush", "data": {"path": path, "flushed": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FLUSH_ERROR", str(e), 0))

    def glob(self, params=None):
        params = params or {}
        try:
            pattern = params.get("pattern", "*")
            root = params.get("root", ".")
            matched = []
            for dirpath, dirnames, filenames in os.walk(root):
                for name in dirnames + filenames:
                    full = os.path.join(dirpath, name)
                    if fnmatch.fnmatch(full, pattern) or fnmatch.fnmatch(name, pattern):
                        matched.append(full)
            result = {"domain": "io", "method": "glob", "data": {"pattern": pattern, "matches": matched}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GLOB_ERROR", str(e), 0))

    def join(self, params=None):
        params = params or {}
        try:
            parts = params.get("parts", [])
            joined = os.path.join(*parts) if parts else ""
            result = {"domain": "io", "method": "join", "data": {"parts": parts, "joined": joined}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("JOIN_ERROR", str(e), 0))

    def listdir(self, params=None):
        params = params or {}
        try:
            path = params.get("path", ".")
            entries = os.listdir(path)
            result = {"domain": "io", "method": "listdir", "data": {"path": path, "entries": entries}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LISTDIR_ERROR", str(e), 0))

    def makedirs(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            exist_ok = params.get("exist_ok", True)
            os.makedirs(path, exist_ok=exist_ok)
            result = {"domain": "io", "method": "makedirs", "data": {"path": path, "created": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MAKEDIRS_ERROR", str(e), 0))

    def move(self, params=None):
        params = params or {}
        try:
            src = params.get("src", "")
            dst = params.get("dst", "")
            shutil.move(src, dst)
            result = {"domain": "io", "method": "move", "data": {"src": src, "dst": dst}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MOVE_ERROR", str(e), 0))

    def open(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            mode = params.get("mode", "r")
            encoding = params.get("encoding", "utf-8")
            fh = open(path, mode, encoding=encoding if "b" not in mode else None)
            self.state["config"]["_open_handle"] = id(fh)
            self.state["results"].append({"path": path, "mode": mode})
            result = {"domain": "io", "method": "open", "data": {"path": path, "mode": mode, "opened": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("OPEN_ERROR", str(e), 0))

    def read(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            encoding = params.get("encoding", "utf-8")
            with open(path, "r", encoding=encoding) as fh:
                content = fh.read()
            result = {"domain": "io", "method": "read", "data": {"path": path, "content": content, "size": len(content)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("READ_ERROR", str(e), 0))

    def readlines(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            encoding = params.get("encoding", "utf-8")
            with open(path, "r", encoding=encoding) as fh:
                lines = fh.readlines()
            result = {"domain": "io", "method": "readlines", "data": {"path": path, "lines": lines, "count": len(lines)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("READLINES_ERROR", str(e), 0))

    def rmdir(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            os.rmdir(path)
            result = {"domain": "io", "method": "rmdir", "data": {"path": path, "removed": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RMDIR_ERROR", str(e), 0))

    def seek(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            offset = int(params.get("offset", 0))
            whence = int(params.get("whence", 0))
            with open(path, "rb") as fh:
                pos = fh.seek(offset, whence)
            result = {"domain": "io", "method": "seek", "data": {"path": path, "position": pos}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SEEK_ERROR", str(e), 0))

    def split(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            head, tail = os.path.split(path)
            result = {"domain": "io", "method": "split", "data": {"path": path, "head": head, "tail": tail}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SPLIT_ERROR", str(e), 0))

    def stat(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            st = os.stat(path)
            info = {
                "size": st.st_size,
                "mode": st.st_mode,
                "mtime": st.st_mtime,
                "atime": st.st_atime,
                "ctime": st.st_ctime,
            }
            result = {"domain": "io", "method": "stat", "data": {"path": path, "stat": info}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STAT_ERROR", str(e), 0))

    def tell(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            with open(path, "rb") as fh:
                pos = fh.tell()
            result = {"domain": "io", "method": "tell", "data": {"path": path, "position": pos}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TELL_ERROR", str(e), 0))

    def temp(self, params=None):
        params = params or {}
        try:
            suffix = params.get("suffix", "")
            prefix = params.get("prefix", "tmp")
            dirname = params.get("dir", None)
            fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dirname)
            os.close(fd)
            result = {"domain": "io", "method": "temp", "data": {"path": tmp_path}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TEMP_ERROR", str(e), 0))

    def touch(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            if not os.path.exists(path):
                with open(path, "a", encoding="utf-8"):
                    pass
            else:
                os.utime(path, None)
            result = {"domain": "io", "method": "touch", "data": {"path": path, "touched": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TOUCH_ERROR", str(e), 0))

    def truncate(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            length = int(params.get("length", 0))
            with open(path, "r+", encoding="utf-8") as fh:
                fh.truncate(length)
            result = {"domain": "io", "method": "truncate", "data": {"path": path, "length": length}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TRUNCATE_ERROR", str(e), 0))

    def walk(self, params=None):
        params = params or {}
        try:
            path = params.get("path", ".")
            tree = []
            for dirpath, dirnames, filenames in os.walk(path):
                tree.append({"dir": dirpath, "dirs": list(dirnames), "files": list(filenames)})
            result = {"domain": "io", "method": "walk", "data": {"path": path, "tree": tree}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WALK_ERROR", str(e), 0))

    def watch(self, params=None):
        params = params or {}
        try:
            path = params.get("path", ".")
            duration = float(params.get("duration", 1.0))
            initial = {}
            for dirpath, dirnames, filenames in os.walk(path):
                for name in filenames:
                    full = os.path.join(dirpath, name)
                    try:
                        initial[full] = os.path.getmtime(full)
                    except OSError:
                        initial[full] = None
            time.sleep(duration)
            changes = {"added": [], "modified": [], "removed": []}
            current = {}
            for dirpath, dirnames, filenames in os.walk(path):
                for name in filenames:
                    full = os.path.join(dirpath, name)
                    try:
                        mtime = os.path.getmtime(full)
                    except OSError:
                        mtime = None
                    current[full] = mtime
                    if full not in initial:
                        changes["added"].append(full)
                    elif initial.get(full) != mtime:
                        changes["modified"].append(full)
            for old_path in initial:
                if old_path not in current:
                    changes["removed"].append(old_path)
            result = {"domain": "io", "method": "watch", "data": {"path": path, "changes": changes}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WATCH_ERROR", str(e), 0))

    def write(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            content = params.get("content", "")
            mode = params.get("mode", "w")
            encoding = params.get("encoding", "utf-8")
            with open(path, mode, encoding=encoding) as fh:
                fh.write(content)
            result = {"domain": "io", "method": "write", "data": {"path": path, "written": len(content)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WRITE_ERROR", str(e), 0))

    def writelines(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            lines = params.get("lines", [])
            mode = params.get("mode", "w")
            encoding = params.get("encoding", "utf-8")
            with open(path, mode, encoding=encoding) as fh:
                fh.writelines(lines)
            result = {"domain": "io", "method": "writelines", "data": {"path": path, "count": len(lines)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WRITELINES_ERROR", str(e), 0))
