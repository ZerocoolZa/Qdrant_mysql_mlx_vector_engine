# [@GHOST]
# Ghost header — OrchestrationView
# Purpose: Who calls who? — thin wrapper around GraphEngine.orchestration view
# [@VBSTYLE]
# VBStyle: Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE
# Rules: @ghost(33), @vbsty(34), @cstyle(35), @clshdr(36), @mthdr(37), @pascal(38), @upper(39), @print(22), @decorators(20), @hardcode(24), @underscore(19), @run(43), @t3(50), @state(41), @ctor(40), @memunit(32), @dismap(31)

import os
import sys
from Config_graph_engine import cfg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from GraphEngine import GraphEngine
from GraphViewer import GraphViewer


class OrchestrationView:
    """Graph view: Who calls who?"""

    def __init__(self):
        self.state = {
            "engine": GraphEngine(),
            "viewer": GraphViewer(),
            "view": "orchestration",
            "question": "Who calls who?",
        }

    def Run(self, command, params):
        """Dispatch entry point. Returns Tuple3(ok, data, error)."""
        if params is None:
            params = {}
        dispatch = {
            "data": self.GetData,
            "render": self.Render,
            "question": self.GetQuestion,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, "unknown_command: {command}".format(command=command))
        return handler(params)

    def GetData(self, params):
        """Fetch view data from GraphEngine."""
        return self.state["engine"].Run("orchestration", params)

    def Render(self, params):
        """Render the view via GraphViewer."""
        ok, data, err = self.GetData(params)
        if not ok:
            return (0, data, err)
        nodes = []
        edges = []
        if "steps" in data:
            nodes = [{"id": s["name"], "type": "step"} for s in data["steps"]]
        elif "classes" in data:
            nodes = [{"id": c["name"], "type": "class"} for c in data["classes"]]
        elif "flows" in data:
            nodes = [{"id": f.get("role", f.get("caller", "?")), "type": "flow"} for f in data["flows"]]
        elif "phases" in data:
            nodes = [{"id": p["phase"], "type": "phase"} for p in data["phases"]]
        elif "dependencies" in data:
            nodes = list(set([{"id": d["from"], "type": "node"} for d in data["dependencies"]] + [{"id": d["to"], "type": "node"} for d in data["dependencies"]]))
            edges = data["dependencies"]
        elif "errors" in data:
            nodes = [{"id": e["error"], "type": "error"} for e in data["errors"]]
        elif "calls" in data:
            seen = set()
            nodes = []
            for c in data["calls"]:
                for key in ("caller", "callee"):
                    nid = c[key]
                    if nid not in seen:
                        seen.add(nid)
                        nodes.append({"id": nid, "type": key})
            edges = data["calls"]
        elif "missing_tables" in data:
            nodes = [{"id": t, "type": "table"} for t in data.get("existing_tables", [])]
            for m in data.get("missing_tables", []):
                nodes.append({"id": m, "type": "missing"})
        render_params = {"view": "orchestration", "nodes": nodes, "edges": edges}
        return self.state["viewer"].Run("render", render_params)

    def GetQuestion(self, params):
        """Return the guiding question for this view."""
        return (1, {"view": "orchestration", "question": "Who calls who?"}, None)
