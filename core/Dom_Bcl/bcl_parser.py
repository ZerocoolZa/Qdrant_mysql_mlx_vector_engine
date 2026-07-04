#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_parser.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstype-fix"
# context="Stage 2: BCL Parser — recursive descent, tokens in, AST out"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_parser.py" domain="BCL" authority="BCLParser"}
# [@SUMMARY]{summary="BCL Parser: token stream in, BCLNode AST tree out. Recursive descent, no regex, no guessing."}
# [@CLASS]{class="BCLParser" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="parse" type="command"}
# [@METHOD]{method="parse_container" type="command"}
# [@METHOD]{method="parse_body" type="command"}
# [@METHOD]{method="parse_tuple" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

from bcl_lexer import (
    CONTAINER_OPEN, BRACE_OPEN, BRACE_CLOSE, PAREN_OPEN, PAREN_CLOSE,
    SEMICOLON, STRING, NUMBER, BAREWORD, EOF,
)


class BCLNode:
    """AST node = one [@container] with tuples and child containers."""

    def __init__(self, name=None, parent=None, mem=None, db=None, param=None):
        self.state = {
            "name": name or "",
            "tuples": [],
            "children": [],
            "parent": parent,
        }
        if param:
            for key, value in param.items():
                self.state[key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "path":
            return self.Path(params)
        elif command == "get":
            return self.Get(params)
        elif command == "get_weight":
            return self.GetWeight(params)
        elif command == "set":
            return self.Set(params)
        elif command == "to_bcl":
            return self.ToBcl(params)
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
            self.state[key] = value
        return (1, dict(self.state), None)

    def Path(self, params=None):
        parts = []
        node = self
        while node is not None and node.state["name"] != "root":
            parts.append(node.state["name"])
            node = node.state["parent"]
        if parts:
            return (1, "/" + "/".join(reversed(parts)), None)
        return (1, "/root", None)

    def Get(self, params):
        key = self._p(params, "key")
        if key is None:
            return (0, None, ("MISSING_PARAM", "key required", 0))
        for t in self.state["tuples"]:
            if t and t[0] == key:
                if len(t) == 2 and isinstance(t[1], (int, float)):
                    return (1, {"value": None,
                               "weight": t[1]}, None)
                if len(t) == 2:
                    return (1, t[1], None)
                return (1, {"value": t[1] if len(t) > 1 else None,
                           "weight": t[-1] if isinstance(t[-1], (int, float)) else None}, None)
        return (1, None, None)

    def GetWeight(self, params=None):
        best = None
        for t in self.state["tuples"]:
            if t and isinstance(t[-1], (int, float)):
                w = t[-1]
                if best is None or w > best:
                    best = w
        return (1, best, None)

    def Set(self, params):
        key = self._p(params, "key")
        value = self._p(params, "value")
        if key is None:
            return (0, None, ("MISSING_PARAM", "key required", 0))
        for i, t in enumerate(self.state["tuples"]):
            if t and t[0] == key:
                if len(t) == 1:
                    self.state["tuples"][i].append(value)
                elif len(t) >= 2:
                    self.state["tuples"][i][1] = value
                return (1, True, None)
        self.state["tuples"].append([key, value])
        return (1, True, None)

    def ToBcl(self, params=None):
        indent = self._p(params, "indent", 0)
        pad = "    " * indent
        lines = ["[@%s]{" % self.state["name"]]
        for t in self.state["tuples"]:
            parts = []
            for v in t:
                if isinstance(v, (int, float)):
                    parts.append(str(v))
                else:
                    s = str(v).replace("\\", "\\\\").replace('"', '\\"').replace(";", "\\;").replace("\n", "\\n").replace("\t", "\\t")
                    parts.append('"%s"' % s)
            lines.append("%s    (%s)" % (pad, ";".join(parts)))
        for child in self.state["children"]:
            child_result = child.ToBcl({"indent": indent + 1})
            if child_result[0] == 1:
                lines.append(child_result[1])
        lines.append("%s}" % pad)
        return (1, "\n".join(lines), None)


class BCLParser:
    """Recursive descent parser. Token stream in, BCLNode AST out."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "tokens": [],
            "pos": 0,
            "root": None,
            "errors": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "parse":
            return self.Parse(params)
        elif command == "parse_container":
            return self.ParseContainer(params)
        elif command == "parse_body":
            return self.ParseBody(params)
        elif command == "parse_tuple":
            return self.ParseTuple(params)
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

    def Peek(self):
        if self.state["pos"] < len(self.state["tokens"]):
            return (1, self.state["tokens"][self.state["pos"]], None)
        if self.state["tokens"]:
            return (1, self.state["tokens"][-1], None)
        return (0, None, ("NO_TOKENS", "Token list is empty", 0))

    def Advance(self):
        peek_result = self.Peek()
        if peek_result[0] == 0:
            return peek_result
        tok = peek_result[1]
        self.state["pos"] += 1
        return (1, tok, None)

    def Expect(self, expected_type):
        peek_result = self.Peek()
        if peek_result[0] == 0:
            return peek_result
        tok = peek_result[1]
        if tok["type"] != expected_type:
            err = ("PARSE_ERROR",
                   "Expected %s got %s (%s)" % (expected_type, tok["type"], tok["value"]), 0)
            self.state["errors"].append(err)
            return (0, None, err)
        return self.Advance()

    def Parse(self, params):
        tokens = self._p(params, "tokens")
        if tokens is None:
            return (0, None, ("MISSING_PARAM", "tokens required", 0))
        self.state["tokens"] = tokens
        self.state["pos"] = 0
        self.state["errors"] = []
        root = BCLNode("root")
        peek_result = self.Peek()
        while peek_result[0] == 1 and peek_result[1]["type"] != EOF:
            if peek_result[1]["type"] == CONTAINER_OPEN:
                container_result = self.ParseContainer({"parent": root})
                if container_result[0] == 1 and container_result[1] is not None:
                    root.state["children"].append(container_result[1])
                elif container_result[0] == 0:
                    return container_result
            else:
                self.Advance()
            peek_result = self.Peek()
        self.state["root"] = root
        return (1, {"root": root, "children": len(root.state["children"]),
                    "errors": self.state["errors"]}, None)

    def ParseContainer(self, params):
        parent = self._p(params, "parent")
        expect_result = self.Expect(CONTAINER_OPEN)
        if expect_result[0] == 0:
            return expect_result
        tok = expect_result[1]
        node = BCLNode(tok["value"], parent=parent)
        peek_result = self.Peek()
        if peek_result[0] == 0:
            return peek_result
        next_tok = peek_result[1]
        if next_tok["type"] == BRACE_OPEN:
            self.Advance()
            body_result = self.ParseBody({"node": node})
            if body_result[0] == 0:
                return body_result
        elif next_tok["type"] == PAREN_OPEN:
            tuple_result = self.ParseTuple({})
            if tuple_result[0] == 0:
                return tuple_result
            if tuple_result[1] is not None:
                node.state["tuples"].append(tuple_result[1])
        return (1, node, None)

    def ParseBody(self, params):
        node = self._p(params, "node")
        if node is None:
            return (0, None, ("MISSING_PARAM", "node required", 0))
        while True:
            peek_result = self.Peek()
            if peek_result[0] == 0:
                return peek_result
            tok = peek_result[1]
            if tok["type"] == BRACE_CLOSE:
                self.Advance()
                return (1, node, None)
            elif tok["type"] == EOF:
                err = ("UNCLOSED_CONTAINER", "Unclosed container [@%s]" % node.state["name"], 0)
                self.state["errors"].append(err)
                return (0, None, err)
            elif tok["type"] == PAREN_OPEN:
                tuple_result = self.ParseTuple({})
                if tuple_result[0] == 0:
                    return tuple_result
                if tuple_result[1] is not None:
                    node.state["tuples"].append(tuple_result[1])
            elif tok["type"] == CONTAINER_OPEN:
                child_result = self.ParseContainer({"parent": node})
                if child_result[0] == 0:
                    return child_result
                if child_result[1] is not None:
                    node.state["children"].append(child_result[1])
            else:
                self.Advance()

    def ParseTuple(self, params):
        expect_result = self.Expect(PAREN_OPEN)
        if expect_result[0] == 0:
            return expect_result
        values = []
        while True:
            peek_result = self.Peek()
            if peek_result[0] == 0:
                return peek_result
            tok = peek_result[1]
            if tok["type"] == PAREN_CLOSE:
                self.Advance()
                if values:
                    return (1, values, None)
                return (1, None, None)
            elif tok["type"] == EOF:
                err = ("UNCLOSED_TUPLE", "Unclosed tuple missing )", 0)
                self.state["errors"].append(err)
                return (0, None, err)
            elif tok["type"] == SEMICOLON:
                self.Advance()
            elif tok["type"] in (STRING, NUMBER, BAREWORD):
                adv_result = self.Advance()
                if adv_result[0] == 0:
                    return adv_result
                values.append(adv_result[1]["value"])
            else:
                self.Advance()
