# [@GHOST]
# Ghost header — Inspect
# Purpose: Post-code analysis bridge. AST parse real files, build graph, compare.
# Layer: Called by GraphEngine. Bridges to efl_brain system.
# [@VBSTYLE]
# VBStyle: Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE
# Rules: @ghost(33), @vbsty(34), @cstyle(35), @clshdr(36), @mthdr(37), @pascal(38), @upper(39), @print(22), @decorators(20), @hardcode(24), @underscore(19), @run(43), @t3(50), @state(41), @ctor(40), @memunit(32), @dismap(31)

import os
import sys
import ast
import json
from Config_graph_engine import cfg


class Inspect:
    """Post-code analysis. Parses Python files via AST, extracts structure."""

    def __init__(self):
        self.state = {
            "domain": cfg.DOMAIN,
            "results": None,
        }

    def Run(self, command, params):
        """Dispatch entry point. Returns Tuple3(ok, data, error)."""
        if params is None:
            params = {}
        dispatch = {
            "parse": self.Parse,
            "build_graph": self.BuildGraph,
            "compare": self.Compare,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, "unknown_command: {command}".format(command=command))
        return handler(params)

    def Parse(self, params):
        """AST parse a Python file. Extract classes, methods, Run() dispatch."""
        filepath = params.get("filepath")
        if not filepath:
            return (0, None, "missing_param: filepath")
        if not os.path.exists(filepath):
            return (0, None, "file_not_found: {path}".format(path=filepath))
        try:
            with open(filepath, "r") as f:
                source = f.read()
            tree = ast.parse(source, filename=filepath)
        except SyntaxError as exc:
            return (0, None, "syntax_error: {msg}".format(msg=str(exc)))
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                has_run = False
                has_tuple3 = False
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.append(item.name)
                        if item.name == "Run":
                            has_run = True
                            for ret in ast.walk(item):
                                if isinstance(ret, ast.Tuple) and len(ret.elts) == 3:
                                    has_tuple3 = True
                classes.append({
                    "name": node.name,
                    "methods": methods,
                    "method_count": len(methods),
                    "has_run": has_run,
                    "has_tuple3": has_tuple3,
                    "line": node.lineno,
                })
        self.state["results"] = {"filepath": filepath, "classes": classes, "class_count": len(classes)}
        return (1, self.state["results"], None)

    def BuildGraph(self, params):
        """Build a dependency graph from parsed classes."""
        filepath = params.get("filepath")
        if not filepath:
            results = self.state.get("results")
            if not results:
                return (0, None, "missing_param: filepath or prior parse results")
            filepath = results.get("filepath")
        if not self.state.get("results") or self.state["results"].get("filepath") != filepath:
            ok, data, err = self.Parse({"filepath": filepath})
            if not ok:
                return (0, data, err)
        results = self.state["results"]
        nodes = []
        edges = []
        for cls in results["classes"]:
            nodes.append({"id": cls["name"], "type": "class", "line": cls["line"]})
            for method in cls["methods"]:
                nodes.append({"id": "{cls}.{method}".format(cls=cls["name"], method=method), "type": "method"})
                edges.append({"from": cls["name"], "to": "{cls}.{method}".format(cls=cls["name"], method=method), "type": "contains"})
        return (1, {"filepath": filepath, "nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}, None)

    def Compare(self, params):
        """Compare parsed structure against DB classes."""
        filepath = params.get("filepath")
        if not filepath:
            return (0, None, "missing_param: filepath")
        ok, data, err = self.Parse({"filepath": filepath})
        if not ok:
            return (0, data, err)
        import sqlite3
        db = sqlite3.connect(cfg.DB_PATH)
        cur = db.cursor()
        db_classes = cur.execute(
            "SELECT class_name FROM classes WHERE domain=?", (self.state["domain"],)
        ).fetchall()
        db_class_names = {row[0] for row in db_classes}
        db.close()
        file_class_names = {cls["name"] for cls in data["classes"]}
        missing_in_db = list(file_class_names - db_class_names)
        missing_in_file = list(db_class_names - file_class_names)
        matched = list(file_class_names & db_class_names)
        return (
            1,
            {
                "filepath": filepath,
                "matched": matched,
                "missing_in_db": missing_in_db,
                "missing_in_file": missing_in_file,
                "matched_count": len(matched),
                "missing_in_db_count": len(missing_in_db),
                "missing_in_file_count": len(missing_in_file),
            },
            None,
        )
