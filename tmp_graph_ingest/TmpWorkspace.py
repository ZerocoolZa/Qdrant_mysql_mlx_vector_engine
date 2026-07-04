# [@GHOST]
# Ghost header — TmpWorkspace
# Purpose: Safe sandbox for AI runs. Each run gets its own tmp folder.
# Layer: Supports DecisionEngine by providing isolated workspace.
# [@VBSTYLE]
# VBStyle: Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE
# Rules: @ghost(33), @vbsty(34), @cstyle(35), @clshdr(36), @mthdr(37), @pascal(38), @upper(39), @print(22), @decorators(20), @hardcode(24), @underscore(19), @run(43), @t3(50), @state(41), @ctor(40), @memunit(32), @dismap(31)

import os
import sys
import uuid
import shutil
import py_compile
from Config_graph_engine import cfg


class TmpWorkspace:
    """Safe sandbox for AI code iteration. Each run gets own folder."""

    def __init__(self):
        self.state = {
            "tmp_dir": cfg.TMP_DIR,
            "run_id": None,
            "run_path": None,
        }

    def Run(self, command, params):
        """Dispatch entry point. Returns Tuple3(ok, data, error)."""
        if params is None:
            params = {}
        dispatch = {
            "create": self.Create,
            "write": self.Write,
            "read": self.Read,
            "list": self.List,
            "clean": self.Clean,
            "compile": self.Compile,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, "unknown_command: {command}".format(command=command))
        return handler(params)

    def Create(self, params):
        """Create a run folder. Returns (run_id, path)."""
        run_id = "run_" + uuid.uuid4().hex[:12]
        run_path = os.path.join(self.state["tmp_dir"], run_id)
        os.makedirs(run_path, exist_ok=True)
        self.state["run_id"] = run_id
        self.state["run_path"] = run_path
        return (1, {"run_id": run_id, "path": run_path}, None)

    def Write(self, params):
        """Write a file in the run folder. Returns full path."""
        run_path = params.get("run_path", self.state.get("run_path"))
        filename = params.get("filename")
        content = params.get("content", "")
        if not run_path or not filename:
            return (0, None, "missing_param: run_path and filename")
        full_path = os.path.join(run_path, filename)
        os.makedirs(os.path.dirname(full_path), exist_ok=True) if os.path.dirname(filename) else None
        with open(full_path, "w") as f:
            f.write(content)
        return (1, {"path": full_path, "size": len(content)}, None)

    def Read(self, params):
        """Read a file from the run folder. Returns content."""
        run_path = params.get("run_path", self.state.get("run_path"))
        filename = params.get("filename")
        if not run_path or not filename:
            return (0, None, "missing_param: run_path and filename")
        full_path = os.path.join(run_path, filename)
        if not os.path.exists(full_path):
            return (0, None, "file_not_found: {path}".format(path=full_path))
        with open(full_path, "r") as f:
            content = f.read()
        return (1, {"path": full_path, "content": content, "size": len(content)}, None)

    def List(self, params):
        """List files in a run folder. Returns file list."""
        run_path = params.get("run_path", self.state.get("run_path"))
        if not run_path:
            return (0, None, "missing_param: run_path")
        if not os.path.exists(run_path):
            return (0, None, "path_not_found: {path}".format(path=run_path))
        files = []
        for item in os.listdir(run_path):
            full = os.path.join(run_path, item)
            size = os.path.getsize(full) if os.path.isfile(full) else 0
            files.append({"name": item, "size": size, "is_dir": os.path.isdir(full)})
        return (1, {"path": run_path, "files": files, "count": len(files)}, None)

    def Clean(self, params):
        """Remove a run folder. Returns confirmation."""
        run_id = params.get("run_id")
        run_path = params.get("run_path", self.state.get("run_path"))
        if not run_path and run_id:
            run_path = os.path.join(self.state["tmp_dir"], run_id)
        if not run_path:
            return (0, None, "missing_param: run_id or run_path")
        if os.path.exists(run_path):
            shutil.rmtree(run_path)
        if self.state.get("run_id") == run_id:
            self.state["run_id"] = None
            self.state["run_path"] = None
        return (1, {"cleaned": True, "path": run_path}, None)

    def Compile(self, params):
        """py_compile a file. Returns (ok, error)."""
        filepath = params.get("filepath")
        if not filepath:
            return (0, None, "missing_param: filepath")
        if not os.path.exists(filepath):
            return (0, None, "file_not_found: {path}".format(path=filepath))
        try:
            py_compile.compile(filepath, doraise=True)
            return (1, {"compiled": True, "path": filepath}, None)
        except py_compile.PyCompileError as exc:
            return (0, None, "compile_error: {msg}".format(msg=str(exc)))
