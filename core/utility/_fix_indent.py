#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Core/utility/_fix_indent.py"
# date="2026-06-27" author="Cascade" session_id="bcl-fix-indent"
# context="Fix indentation in Python files by detecting structure markers"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="_fix_indent.py" domain="utility" authority="build"}
# [@SUMMARY]{summary="Fixes indentation by detecting class/def/control flow and indenting accordingly."}
# [@CLASS]{class="FixIndent" domain="utility" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="Fix" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}

import os


class FixIndent:
    """Fix indentation in Python files by detecting structure markers."""

    BLOCK_STARTERS = {"if", "for", "while", "try", "except", "else", "elif", "finally", "with"}

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "fixed_count": 0,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "fix":
            return self.Fix(params)
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

    def Fix(self, params):
        filepath = self._p(params, "path")
        if filepath is None:
            return (0, None, ("MISSING_PARAM", "path required", 0))
        with open(filepath, "r") as f:
            raw_lines = f.read().split("\n")
        out = []
        indent_stack = [0]
        for line in raw_lines:
            stripped = line.strip()
            if stripped == "" or stripped.startswith("#"):
                out.append("")
                continue
            first_word = stripped.split("(")[0].split(" ")[0].split(":")[0]
            if stripped.startswith("def ") or stripped.startswith("class "):
                current_indent = indent_stack[-1]
                out.append(" " * current_indent + stripped)
                if stripped.rstrip().endswith(":"):
                    indent_stack.append(current_indent + 4)
                continue
            if first_word in self.BLOCK_STARTERS and stripped.rstrip().endswith(":"):
                current_indent = indent_stack[-1]
                out.append(" " * current_indent + stripped)
                indent_stack.append(current_indent + 4)
                continue
            if first_word in ("except", "else", "elif", "finally"):
                if len(indent_stack) > 1:
                    indent_stack.pop()
                current_indent = indent_stack[-1]
                out.append(" " * current_indent + stripped)
                if stripped.rstrip().endswith(":"):
                    indent_stack.append(current_indent + 4)
                continue
            current_indent = indent_stack[-1]
            out.append(" " * current_indent + stripped)
        with open(filepath, "w") as f:
            f.write("\n".join(out))
        self.state["fixed_count"] += 1
        return (1, {"path": filepath, "lines": len(out)}, None)


if __name__ == "__main__":
    fixer = FixIndent()
    target = sys.argv[1] if len(sys.argv) > 1 else "bcl_all.py"
    fixer.Run("fix", {"path": target})
