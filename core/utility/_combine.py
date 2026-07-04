#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Core/utility/_combine.py"
# date="2026-06-27" author="Cascade" session_id="utility-combine"
# context="Generic file combiner. Reads target config from Config.py, accepts overrides via params."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="_combine.py" domain="utility" authority="build"}
# [@SUMMARY]{summary="Combines any source files into one output file. Target name or full params accepted."}
# [@CLASS]{class="CombineUtil" domain="utility" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="StripFile" type="command"}
# [@METHOD]{method="ApplyRenames" type="command"}
# [@METHOD]{method="Build" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Config import TARGETS


class CombineUtil:
    """Combine any source files into a single output file. Globally reusable."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "target": None,
            "source_dir": None,
            "output_path": None,
            "files": None,
            "renames": None,
            "import_header": None,
            "patches": None,
            "lines": 0,
            "classes": 0,
        }
        if param:
            self.SetTarget(param)

    def SetTarget(self, param):
        target_name = param.get("target")
        if target_name and target_name in TARGETS:
            t = TARGETS[target_name]
            self.state["target"] = target_name
            self.state["source_dir"] = t["source_dir"]
            self.state["output_path"] = t["output_path"]
            self.state["files"] = t["files"]
            self.state["renames"] = t.get("renames", {})
            self.state["import_header"] = t.get("import_header", "")
            self.state["patches"] = t.get("patches", [])
        for key in ("source_dir", "output_path", "files", "renames", "import_header", "patches"):
            if key in param:
                self.state[key] = param[key]

    def Run(self, command, params=None):
        params = params or {}
        if command == "build":
            return self.Build(params)
        elif command == "strip_file":
            return self.StripFile(params)
        elif command == "apply_renames":
            return self.ApplyRenames(params)
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
        self.SetTarget(params)
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def StripFile(self, params):
        content = self._p(params, "content")
        if content is None:
            return (0, None, ("MISSING_PARAM", "content required", 0))
        lines = content.split("\n")
        out = []
        in_header = True
        in_multi_import = False
        for line in lines:
            stripped = line.strip()
            if in_multi_import:
                if stripped == ")" or stripped.endswith(")"):
                    in_multi_import = False
                continue
            if in_header:
                if stripped.startswith("#") or stripped == "":
                    continue
                if stripped.startswith("from ") or stripped.startswith("import "):
                    if stripped.endswith("(") and ")" not in stripped:
                        in_multi_import = True
                    continue
                in_header = False
            else:
                if stripped.startswith("from ") or stripped.startswith("import "):
                    if stripped.endswith("(") and ")" not in stripped:
                        in_multi_import = True
                    continue
            out.append(line)
        while out and out[0].strip() == "":
            out.pop(0)
        while out and out[-1].strip() == "":
            out.pop()
        return (1, "\n".join(out), None)

    def ApplyRenames(self, params):
        text = self._p(params, "text")
        renames = self._p(params, "renames", self.state.get("renames", {}))
        if text is None:
            return (0, None, ("MISSING_PARAM", "text required", 0))
        for old, new in sorted(renames.items(), key=lambda x: -len(x[0])):
            text = re.sub(r'\b' + re.escape(old) + r'\b', new, text)
        return (1, text, None)

    def Build(self, params):
        target = self._p(params, "target")
        if target:
            self.SetTarget(params)
        for key in ("source_dir", "output_path", "files", "renames", "import_header", "patches"):
            val = self._p(params, key)
            if val is not None:
                self.state[key] = val

        source_dir = self.state["source_dir"]
        out_path = self.state["output_path"]
        files = self.state["files"]
        renames = self.state.get("renames", {})
        import_header = self.state.get("import_header", "")
        patches = self.state.get("patches", [])

        if not source_dir or not out_path or not files:
            return (0, None, ("MISSING_CONFIG", "source_dir, output_path, files required. Set target or pass params.", 0))

        header = '#!/usr/bin/env python3\n'
        header += '# [@GHOST]{file_path="' + out_path + '"\n'
        header += '# date="2026-06-27" author="Cascade" session_id="combine"\n'
        header += '# context="Combined module from ' + os.path.basename(source_dir) + '"}\n'
        header += '# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}\n'
        header += '# [@FILEID]{id="' + os.path.basename(out_path) + '" domain="combined" authority="combined"}\n'
        header += '# [@SUMMARY]{summary="Combined source files. Imports from config only."}\n\n'
        header += 'import ast\nimport hashlib\nimport json\nimport os\n'
        header += 'import sqlite3\nimport sys\nimport datetime\n'
        header += 'from collections import Counter\n\n'
        header += import_header

        sections = []
        for fname in files:
            fpath = os.path.join(source_dir, fname)
            if not os.path.exists(fpath):
                continue
            with open(fpath, "r") as f:
                content = f.read()
            strip_result = self.StripFile({"content": content})
            if strip_result[0] == 0:
                return strip_result
            stripped = strip_result[1]
            rename_result = self.ApplyRenames({"text": stripped, "renames": renames})
            if rename_result[0] == 0:
                return rename_result
            stripped = rename_result[1]
            section = "\n# " + "=" * 70 + "\n"
            section += "# SECTION: %s\n" % fname
            section += "# " + "=" * 70 + "\n\n"
            section += stripped
            section += "\n\n"
            sections.append(section)

        output = header + "".join(sections)

        for patch in patches:
            output = output.replace(patch["find"], patch["replace"])

        with open(out_path, "w") as f:
            f.write(output)

        line_count = output.count("\n") + 1
        class_count = output.count("\nclass ")
        self.state["lines"] = line_count
        self.state["classes"] = class_count

        return (1, {"path": out_path, "lines": line_count, "classes": class_count}, None)


if __name__ == "__main__":
    util = CombineUtil(param={"target": "BCL"})
    result = util.Run("build", {})
    if result[0] == 1:
        info = result[1]
        sys.stderr.write("Written: %s\nLines: %d\nClasses: %d\n" % (info["path"], info["lines"], info["classes"]))
    else:
        sys.stderr.write("ERROR: %s\n" % str(result[2]))
        sys.exit(1)
