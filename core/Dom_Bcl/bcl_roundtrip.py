#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_roundtrip.py"
# date="2026-06-27" author="Cascade" session_id="bcl-missing-classes"
# context="BCL RoundTrip — parse serialize parse compare verification"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_roundtrip.py" domain="BCL" authority="BCLRoundTrip"}
# [@SUMMARY]{summary="BCL RoundTrip: verifies parse-serialize-parse produces identical AST. Reports structural differences, tuple losses, name mismatches."}
# [@CLASS]{class="BCLRoundTrip" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="verify" type="command"}
# [@METHOD]{method="compare_trees" type="command"}
# [@METHOD]{method="serialize_tree" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import hashlib

from bcl_lexer import BCLTokenizer
from bcl_parser import BCLParser, BCLNode
from bcl_diff import BCLDiff


class BCLRoundTrip:
    """Round-trip verification: parse -> serialize -> parse -> compare."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "result": None,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "verify":
            return self.Verify(params)
        elif command == "compare_trees":
            return self.CompareTrees(params)
        elif command == "serialize_tree":
            return self.SerializeTree(params)
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
        text = self._p(params, "text")
        if text is None:
            return (0, None, ("MISSING_PARAM", "text required", 0))
        tokenizer = BCLTokenizer()
        tok_result = tokenizer.Run("tokenize", {"text": text})
        if tok_result[0] == 0:
            return (0, None, ("TOKENIZE_ERROR", str(tok_result[2]), 0))
        tokens = tok_result[1]["tokens"]
        parser = BCLParser()
        parse_result = parser.Run("parse", {"tokens": tokens})
        if parse_result[0] == 0:
            return (0, None, ("PARSE_ERROR", str(parse_result[2]), 0))
        first_root = parse_result[1]["root"]
        ser_result = self.SerializeTree({"root": first_root})
        if ser_result[0] == 0:
            return ser_result
        serialized = ser_result[1]
        tok2 = BCLTokenizer()
        tok2_result = tok2.Run("tokenize", {"text": serialized})
        if tok2_result[0] == 0:
            return (0, None, ("TOKENIZE_ERROR_2", str(tok2_result[2]), 0))
        tokens2 = tok2_result[1]["tokens"]
        parser2 = BCLParser()
        parse2_result = parser2.Run("parse", {"tokens": tokens2})
        if parse2_result[0] == 0:
            return (0, None, ("PARSE_ERROR_2", str(parse2_result[2]), 0))
        second_root = parse2_result[1]["root"]
        compare_result = self.CompareTrees({"first": first_root, "second": second_root})
        if compare_result[0] == 0:
            return compare_result
        comparison = compare_result[1]
        first_hash = self.TreeHash(first_root)
        second_hash = self.TreeHash(second_root)
        result = {
            "ok": comparison["identical"],
            "first_hash": first_hash,
            "second_hash": second_hash,
            "hashes_match": first_hash == second_hash,
            "serialized": serialized,
            "differences": comparison["differences"],
            "diff_count": comparison["diff_count"],
            "first_node_count": comparison["first_node_count"],
            "second_node_count": comparison["second_node_count"],
        }
        self.state["result"] = result
        return (1, result, None)

    def SerializeTree(self, params):
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("MISSING_PARAM", "root required", 0))
        lines = []
        for child in root.state["children"]:
            bcl_result = child.ToBcl({"indent": 0})
            if bcl_result[0] == 1:
                lines.append(bcl_result[1])
        return (1, "\n".join(lines), None)

    def CompareTrees(self, params):
        first = self._p(params, "first")
        second = self._p(params, "second")
        if first is None or second is None:
            return (0, None, ("MISSING_PARAM", "first and second required", 0))
        differences = []
        first_count = self.CountNodes(first)
        second_count = self.CountNodes(second)
        if first_count != second_count:
            differences.append({"type": "node_count_mismatch", "first": first_count, "second": second_count})
        self.CompareNodes(first, second, differences, "")
        return (1, {
            "identical": len(differences) == 0,
            "differences": differences,
            "diff_count": len(differences),
            "first_node_count": first_count,
            "second_node_count": second_count,
        }, None)

    def CompareNodes(self, first, second, differences, path_prefix):
        if first.state["name"] != second.state["name"]:
            differences.append({"type": "name_mismatch", "path": path_prefix, "first": first.state["name"], "second": second.state["name"]})
        first_tuples = set(str(t) for t in first.state["tuples"])
        second_tuples = set(str(t) for t in second.state["tuples"])
        if first_tuples != second_tuples:
            differences.append({
                "type": "tuple_mismatch",
                "path": path_prefix,
                "first_only": list(first_tuples - second_tuples),
                "second_only": list(second_tuples - first_tuples),
            })
        first_children = {c.state["name"]: c for c in first.state["children"]}
        second_children = {c.state["name"]: c for c in second.state["children"]}
        for name, fc in first_children.items():
            if name not in second_children:
                differences.append({"type": "child_missing_in_second", "path": path_prefix, "name": name})
            else:
                self.CompareNodes(fc, second_children[name], differences, path_prefix + "/" + name)
        for name in second_children:
            if name not in first_children:
                differences.append({"type": "child_missing_in_first", "path": path_prefix, "name": name})
        return (1, True, None)

    def CountNodes(self, node):
        count = 1
        for child in node.state["children"]:
            count += self.CountNodes(child)
        return count

    def TreeHash(self, root):
        def Walk(n):
            out = [n.state["name"], str(n.state["tuples"])]
            for c in n.state["children"]:
                out.append(Walk(c))
            return "|".join(out)
        return hashlib.md5(Walk(root).encode()).hexdigest()
