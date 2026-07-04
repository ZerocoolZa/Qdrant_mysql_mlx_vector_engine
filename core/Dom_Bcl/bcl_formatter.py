#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_formatter.py"
# date="2026-06-27" author="Cascade" session_id="bcl-missing-classes"
# context="BCL Formatter — configurable BCL output formatting with indent style, line width, spacing options"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_formatter.py" domain="BCL" authority="BCLFormatter"}
# [@SUMMARY]{summary="BCL Formatter: serializes BCLNode trees with configurable indent (spaces/tabs count), line width, tuple spacing, brace style."}
# [@CLASS]{class="BCLFormatter" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="format" type="command"}
# [@METHOD]{method="format_node" type="command"}
# [@METHOD]{method="format_tuple" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

from bcl_parser import BCLNode


class BCLFormatter:
    """Configurable BCL output formatter."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "indent_str": "    ",
                "indent_count": 1,
                "tuple_space": " ",
                "brace_style": "same_line",
                "max_line_width": 120,
                "weight_format": "int",
                "quote_strings": True,
            },
            "output": "",
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "format":
            return self.Format(params)
        elif command == "format_node":
            return self.FormatNode(params)
        elif command == "format_tuple":
            return self.FormatTuple(params)
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

    def Format(self, params):
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("MISSING_PARAM", "root required", 0))
        indent_unit = self.state["config"]["indent_str"] * self.state["config"]["indent_count"]
        lines = []
        for child in root.state["children"]:
            self.FormatNodeRecursive(child, lines, 0, indent_unit)
        output = "\n".join(lines)
        self.state["output"] = output
        return (1, {"text": output, "lines": len(lines)}, None)

    def FormatNodeRecursive(self, node, lines, depth, indent_unit):
        pad = indent_unit * depth
        config = self.state["config"]
        brace = "{" if config["brace_style"] == "same_line" else "\n" + pad + indent_unit + "{"
        lines.append("%s[@%s]%s" % (pad, node.state["name"], brace))
        for t in node.state["tuples"]:
            tuple_str = self.FormatTupleValues(t)
            lines.append("%s%s(%s)" % (pad, indent_unit, tuple_str))
        for child in node.state["children"]:
            self.FormatNodeRecursive(child, lines, depth + 1, indent_unit)
        lines.append("%s}" % pad)
        return (1, True, None)

    def FormatTupleValues(self, values):
        config = self.state["config"]
        parts = []
        for v in values:
            if isinstance(v, (int, float)):
                parts.append(str(int(v)) if config["weight_format"] == "int" and isinstance(v, (int, float)) else str(v))
            else:
                if config["quote_strings"]:
                    parts.append('"%s"' % v)
                else:
                    parts.append(str(v))
        sep = ";" + config["tuple_space"]
        return sep.join(parts)

    def FormatNode(self, params):
        node = self._p(params, "node")
        depth = self._p(params, "depth", 0)
        if node is None:
            return (0, None, ("MISSING_PARAM", "node required", 0))
        indent_unit = self.state["config"]["indent_str"] * self.state["config"]["indent_count"]
        lines = []
        self.FormatNodeRecursive(node, lines, depth, indent_unit)
        return (1, "\n".join(lines), None)

    def FormatTuple(self, params):
        values = self._p(params, "values")
        if values is None:
            return (0, None, ("MISSING_PARAM", "values required", 0))
        return (1, self.FormatTupleValues(values), None)
