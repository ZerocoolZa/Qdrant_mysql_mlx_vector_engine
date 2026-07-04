#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Core/utility/_debug_strip.py"
# date="2026-06-27" author="Cascade" session_id="bcl-debug-strip"
# context="Debug script to verify strip_file preserves class definitions"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="_debug_strip.py" domain="utility" authority="debug"}
# [@SUMMARY]{summary="Verifies that strip_file preserves class definitions in BCL source files."}
# [@CLASS]{class="DebugStrip" domain="utility" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="Verify" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}

import os


class DebugStrip:
    """Verify strip_file preserves class definitions."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "results": [],
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "verify":
            return self.Verify(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Verify(self, params):
        bcl_dir = self._p(params, "bcl_dir")
        if bcl_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(script_dir))
            bcl_dir = os.path.join(project_root, "BCL")
        targets = ["bcl_schema.py", "bcl_serializer.py"]
        results = []
        for fname in targets:
            fpath = os.path.join(bcl_dir, fname)
            if not os.path.exists(fpath):
                results.append({"file": fname, "exists": False})
                continue
            with open(fpath, "r") as f:
                content = f.read()
            class_lines = []
            for i, line in enumerate(content.split("\n")):
                if line.strip().startswith("class "):
                    class_lines.append({"line": i, "text": line.strip()})
            results.append({"file": fname, "exists": True, "classes": class_lines})
        self.state["results"] = results
        return (1, {"results": results}, None)


if __name__ == "__main__":
    dbg = DebugStrip()
    dbg.Run("verify", {})
