#!/usr/bin/env python3
# [@GHOST]{[@file<test_file_io.py>][@domain<utility>][@role<test>][@auth<devin>][@date<2026-07-02>][@ver<1.0.0>][@session<fileio-test>]}
# [@VBSTYLE]{[@auth<devin>][@role<test_suite>][@return<tuple3>][@orch<FileIO>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Test suite for FileIO — pure disk I/O class. Covers walk, read_file, file_stat, hash_file, exists, read_state, and error paths.}
# [@CLASS]{TestFileIO}
# [@METHOD]{Run,TestWalk,TestWalkWithExtensions,TestReadFile,TestReadFileBinary,TestReadFileMissing,TestFileStat,TestFileStatMissing,TestHashFile,TestHashFileLarge,TestHashFileMissing,TestExists,TestExistsMissing,TestReadState,TestUnknownCommand,read_state,set_config}
# [@FILEID]{core/utility/test_file_io.py}

import os
import sys
import tempfile
import hashlib

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.utility.indexer import FileIO


class TestFileIO:
    """Test suite for FileIO. VBStyle compliant — Tuple3 returns, no print, no decorators."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "results": [],
            "errors": [],
            "io": None,
            "tmpdir": None,
        }

    def Run(self, command, params=None):
        dispatch = {
            "run_all": self._RunAll,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", command, 0))
        return handler(params or {})

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state:
                self.state[key] = val
        return (1, dict(self.state), None)

    def _Log(self, name, ok, detail=""):
        status = "PASS" if ok else "FAIL"
        line = "[" + status + "] " + name + (" — " + detail if detail else "")
        self.state["results"].append(line)
        if not ok:
            self.state["errors"].append(line)
        return line

    def _Setup(self):
        tmpdir = tempfile.mkdtemp(prefix="fileio_test_")
        self.state["tmpdir"] = tmpdir
        sub = os.path.join(tmpdir, "sub")
        os.makedirs(sub)
        with open(os.path.join(tmpdir, "alpha.txt"), "w") as f:
            f.write("hello world\n")
        with open(os.path.join(tmpdir, "beta.py"), "w") as f:
            f.write("def Foo():\n    pass\n")
        with open(os.path.join(sub, "gamma.md"), "w") as f:
            f.write("# title\n")
        with open(os.path.join(tmpdir, "data.bin"), "wb") as f:
            f.write(b"\x00\x01\x02\x03")
        self.state["io"] = FileIO()
        return tmpdir

    def _Teardown(self):
        tmpdir = self.state.get("tmpdir")
        if tmpdir and os.path.isdir(tmpdir):
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _RunAll(self, params):
        self._Setup()
        try:
            self.TestWalk(params)
            self.TestWalkWithExtensions(params)
            self.TestWalkSkipDirs(params)
            self.TestReadFile(params)
            self.TestReadFileBinary(params)
            self.TestReadFileMissing(params)
            self.TestFileStat(params)
            self.TestFileStatMissing(params)
            self.TestHashFile(params)
            self.TestHashFileLarge(params)
            self.TestHashFileMissing(params)
            self.TestExists(params)
            self.TestExistsMissing(params)
            self.TestReadState(params)
            self.TestUnknownCommand(params)
            self.TestStateCounters(params)
        finally:
            self._Teardown()
        total = len(self.state["results"])
        failed = len(self.state["errors"])
        passed = total - failed
        summary = "Total: %d, Passed: %d, Failed: %d" % (total, passed, failed)
        ok = failed == 0
        return (1 if ok else 0, {"summary": summary, "passed": passed, "failed": failed, "results": list(self.state["results"])}, None if ok else ("ERR_TESTS", summary, 0))

    # ── walk ──────────────────────────────────────────────────────────────

    def TestWalk(self, params):
        io = self.state["io"]
        tmpdir = self.state["tmpdir"]
        ok, data, err = io.Run("walk", {"path": tmpdir})
        if not ok:
            self._Log("walk_basic", False, "Tuple3 ok=0 err=%s" % str(err))
            return
        files = data["files"]
        names = sorted(os.path.basename(f) for f in files)
        expected = sorted(["alpha.txt", "beta.py", "gamma.md", "data.bin"])
        match = names == expected
        self._Log("walk_basic", match, "got=%s expected=%s count=%d" % (names, expected, data["count"]))
        # DS_Store should be excluded
        if ".DS_Store" in names:
            self._Log("walk_excludes_dsstore", False, ".DS_Store present")
        else:
            self._Log("walk_excludes_dsstore", True, "no .DS_Store")

    def TestWalkWithExtensions(self, params):
        io = self.state["io"]
        tmpdir = self.state["tmpdir"]
        ok, data, err = io.Run("walk", {"path": tmpdir, "extensions": {".py", ".md"}})
        if not ok:
            self._Log("walk_extensions", False, "err=%s" % str(err))
            return
        names = sorted(os.path.basename(f) for f in data["files"])
        expected = sorted(["beta.py", "gamma.md"])
        match = names == expected
        self._Log("walk_extensions", match, "got=%s expected=%s" % (names, expected))

    def TestWalkSkipDirs(self, params):
        io = self.state["io"]
        tmpdir = self.state["tmpdir"]
        skip = os.path.join(tmpdir, "skipme")
        os.makedirs(skip)
        with open(os.path.join(skip, "ignored.txt"), "w") as f:
            f.write("ignored\n")
        ok, data, err = io.Run("walk", {"path": tmpdir, "skip_dirs": {"skipme"}})
        if not ok:
            self._Log("walk_skipdirs", False, "err=%s" % str(err))
            return
        names = [os.path.basename(f) for f in data["files"]]
        match = "ignored.txt" not in names
        self._Log("walk_skipdirs", match, "files=%s" % names)

    def TestWalkInvalidPath(self, params):
        io = self.state["io"]
        ok, data, err = io.Run("walk", {"path": "/no/such/path/here"})
        match = ok == 0 and err is not None
        self._Log("walk_invalid_path", match, "ok=%d err=%s" % (ok, str(err)))

    # ── read_file ─────────────────────────────────────────────────────────

    def TestReadFile(self, params):
        io = self.state["io"]
        tmpdir = self.state["tmpdir"]
        path = os.path.join(tmpdir, "alpha.txt")
        ok, content, err = io.Run("read_file", {"path": path})
        match = ok == 1 and content == "hello world\n"
        self._Log("read_file_text", match, "content=%r" % content)

    def TestReadFileBinary(self, params):
        io = self.state["io"]
        tmpdir = self.state["tmpdir"]
        path = os.path.join(tmpdir, "data.bin")
        ok, content, err = io.Run("read_file", {"path": path, "mode": "rb"})
        match = ok == 1 and content == b"\x00\x01\x02\x03"
        self._Log("read_file_binary", match, "content=%r" % content)

    def TestReadFileMissing(self, params):
        io = self.state["io"]
        ok, content, err = io.Run("read_file", {"path": "/no/such/file.txt"})
        match = ok == 0 and err is not None
        self._Log("read_file_missing", match, "ok=%d err=%s" % (ok, str(err)))

    # ── file_stat ─────────────────────────────────────────────────────────

    def TestFileStat(self, params):
        io = self.state["io"]
        tmpdir = self.state["tmpdir"]
        path = os.path.join(tmpdir, "alpha.txt")
        ok, stat, err = io.Run("file_stat", {"path": path})
        if not ok:
            self._Log("file_stat", False, "err=%s" % str(err))
            return
        checks = (
            stat["size"] == len("hello world\n"),
            stat["is_file"] is True,
            stat["is_dir"] is False,
            "created" in stat,
            "modified" in stat,
        )
        match = all(checks)
        self._Log("file_stat", match, "size=%d is_file=%s" % (stat["size"], stat["is_file"]))

    def TestFileStatMissing(self, params):
        io = self.state["io"]
        ok, stat, err = io.Run("file_stat", {"path": "/no/such/file.txt"})
        match = ok == 0 and err is not None
        self._Log("file_stat_missing", match, "ok=%d err=%s" % (ok, str(err)))

    # ── hash_file ─────────────────────────────────────────────────────────

    def TestHashFile(self, params):
        io = self.state["io"]
        tmpdir = self.state["tmpdir"]
        path = os.path.join(tmpdir, "alpha.txt")
        ok, md5, err = io.Run("hash_file", {"path": path})
        expected = hashlib.md5(b"hello world\n").hexdigest()
        match = ok == 1 and md5 == expected
        self._Log("hash_file_md5", match, "got=%s expected=%s" % (md5, expected))

    def TestHashFileLarge(self, params):
        io = self.state["io"]
        tmpdir = self.state["tmpdir"]
        path = os.path.join(tmpdir, "alpha.txt")
        ok, md5, err = io.Run("hash_file", {"path": path, "threshold": 1})
        match = ok == 1 and md5 == "SKIP_LARGE"
        self._Log("hash_file_skip_large", match, "md5=%s" % md5)

    def TestHashFileMissing(self, params):
        io = self.state["io"]
        ok, md5, err = io.Run("hash_file", {"path": "/no/such/file.txt"})
        match = ok == 0 and err is not None
        self._Log("hash_file_missing", match, "ok=%d err=%s" % (ok, str(err)))

    # ── exists ────────────────────────────────────────────────────────────

    def TestExists(self, params):
        io = self.state["io"]
        tmpdir = self.state["tmpdir"]
        path = os.path.join(tmpdir, "alpha.txt")
        ok, exists, err = io.Run("exists", {"path": path})
        match = ok == 1 and exists is True
        self._Log("exists_true", match, "exists=%s" % exists)

    def TestExistsMissing(self, params):
        io = self.state["io"]
        ok, exists, err = io.Run("exists", {"path": "/no/such/file.txt"})
        match = ok == 1 and exists is False
        self._Log("exists_false", match, "exists=%s" % exists)

    # ── read_state ────────────────────────────────────────────────────────

    def TestReadState(self, params):
        io = self.state["io"]
        ok, state, err = io.Run("read_state")
        match = ok == 1 and "stats" in state and "root" in state and "files" in state
        self._Log("read_state", match, "keys=%s" % sorted(state.keys()))

    # ── unknown command ───────────────────────────────────────────────────

    def TestUnknownCommand(self, params):
        io = self.state["io"]
        ok, data, err = io.Run("bogus_command")
        match = ok == 0 and err is not None and err[0] == "ERR_UNKNOWN_CMD"
        self._Log("unknown_command", match, "ok=%d err=%s" % (ok, str(err)))

    # ── state counters ────────────────────────────────────────────────────

    def TestStateCounters(self, params):
        io = self.state["io"]
        ok, state, err = io.Run("read_state")
        if not ok:
            self._Log("state_counters", False, "read_state failed")
            return
        stats = state["stats"]
        match = stats["walks"] >= 1 and stats["reads"] >= 1 and stats["hashes"] >= 1 and stats["stats"] >= 1
        self._Log("state_counters", match, "stats=%s" % stats)


def main():
    suite = TestFileIO()
    ok, result, err = suite.Run("run_all")
    for line in result["results"]:
        sys.stdout.write(line + "\n")
    sys.stdout.write("\n" + result["summary"] + "\n")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
