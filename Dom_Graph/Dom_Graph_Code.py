#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Typed-State Code Graph with Node/Edge/State primitives. No #[@...] headers (uses old-style comment blocks). No Run dispatch. No Tuple3 returns. Multiple classes (Node, Edge, State, likely more). Uses Config_efl_brain import. File references Efi_code_graph.py in header but filename is Dom_Graph_Code.py. Has hardcoded ROOT path.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Split classes into separate files. Fix filename reference. Remove hardcoded paths.>]}
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     Efi_code_graph.py
# Domain:   efl_brain
# Authority: Typed-state graph builder using Node + Edge + State primitives
# DB:       None
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Graph = (V, E) where V = typed nodes, E = typed edges
# Cycle = detected pattern, NOT a stored primitive
# ============================================================================
"""
Typed-State Code Graph — proper graph primitives.
Primitives:
  Node  — vertex with type + state
  Edge  — directed connection with type
  State — optional runtime data on a node
Derived (NOT stored, detected at query time):
  Cycle, Path, DAG, Hub, Root, Leaf, Cluster, Component
Node types in this architecture:
  FILE_PY       — Python source file
  FILE_JSON     — JSON data file
  FILE_MD       — Markdown documentation file
  FILE_DB       — SQLite database file
  FOLDER        — directory (structural)
  CONFIG        — Config_*.py file (special, boot origin)
  CLASS         — class defined inside a .py file
  FUNCTION      — standalone function inside a .py file
  MEMUNIT       — class with Run() dispatch + self.state dict
"""
import os
import ast
import json
import hashlib
from collections import defaultdict, deque
import Config_efl_brain as Config
ROOT = Config.BASE_DIR
# ============================================================================
# PRIMITIVE: NODE
# ============================================================================
class Node:
    """Graph vertex — the only primitive that carries state."""
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adj = defaultdict(list)
        self.radj = defaultdict(list)
    def ToDict(self):
        return (1, {
            "src": self.src,
            "dst": self.dst,
            "type": self.type,
        }, None)
    def Run(self, command, params=None):
        dispatch = {
            'read_state': self.read_state,
            'set_config': self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params or {})
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
class Edge:
    """Directed edge between two nodes."""
    def __init__(self, src_id, dst_id, edge_type):
        self.src = src_id
        self.dst = dst_id
    def ToDict(self):
        return (1, {
            "src": self.src,
            "dst": self.dst,
            "type": self.type,
        }, None)
    def Run(self, command, params=None):
        dispatch = {
            'read_state': self.read_state,
            'set_config': self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params or {})
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
# ============================================================================
# GRAPH BUILDER
# ============================================================================
class TypedGraph:
    """Graph = (V, E). Everything else is derived."""
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adj = defaultdict(list)
    def AddNode(self, node):
        self.nodes[node.id] = node
        return (1, None, None)
    def AddEdge(self, edge):
        self.edges.append(edge)
        self.adj[edge.src].append(edge.dst)
        self.radj[edge.dst].append(edge.src)
        return (1, None, None)
    def Build(self, root):
        folder_id = root
        self.AddNode(Node(folder_id, "FOLDER", root))
        for entry in sorted(os.listdir(root)):
            full_path = os.path.join(root, entry)
            if os.path.isdir(full_path):
                self.AddNode(Node(full_path, "FOLDER", full_path))
                self.AddEdge(Edge(folder_id, full_path, "CONTAINS"))
                continue
            if entry.startswith("."):
                continue
            ext = os.path.splitext(entry)[1]
            file_id = full_path
            if entry.startswith("Config_") and ext == ".py":
                self.AddNode(Node(file_id, "CONFIG", full_path))
            elif ext == ".py":
                self.AddNode(Node(file_id, "FILE_PY", full_path))
            elif ext == ".json":
                self.AddNode(Node(file_id, "FILE_JSON", full_path))
            elif ext == ".md":
                self.AddNode(Node(file_id, "FILE_MD", full_path))
            elif ext == ".db":
                self.AddNode(Node(file_id, "FILE_DB", full_path))
            else:
                continue
            self.AddEdge(Edge(folder_id, file_id, "CONTAINS"))
        py_nodes = [n for n in self.nodes.values() if n.type in ("FILE_PY", "CONFIG")]
        for py_node in py_nodes:
            self.ParsePythonFile(py_node)
        self.BuildImportEdges(py_nodes)
        return (1, None, None)
    def ParsePythonFile(self, py_node):
        if not os.path.exists(py_node.path):
            return (1, None, None)
        with open(py_node.path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=py_node.path)
            except SyntaxError:
                return (1, None, None)
        for item in ast.iter_child_nodes(tree):
            if isinstance(item, ast.ClassDef):
                class_id = f"{py_node.id}::{item.name}"
                has_run = False
                has_state = False
                methods = []
                for child in item.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(child.name)
                        if child.name == "Run":
                            has_run = True
                        for node in ast.walk(child):
                            if isinstance(node, ast.Attribute):
                                if isinstance(node.value, ast.Name) and node.value.id == "self":
                                    if node.attr == "state":
                                        has_state = True
                node_type = "MEMUNIT" if has_run and has_state else "CLASS"
                class_node = Node(class_id, node_type, py_node.path)
                class_node.state["class_name"] = item.name
                class_node.state["methods"] = methods
                class_node.state["method_count"] = len(methods)
                class_node.state["has_run"] = has_run
                class_node.state["has_state"] = has_state
                class_node.state["bases"] = [b.id for b in item.bases if isinstance(b, ast.Name)]
                self.AddNode(class_node)
                self.AddEdge(Edge(py_node.id, class_id, "DEFINES"))
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_id = f"{py_node.id}::{item.name}"
                func_node = Node(func_id, "FUNCTION", py_node.path)
                func_node.state["function_name"] = item.name
                func_node.state["params"] = [a.arg for a in item.args.args]
                func_node.state["param_count"] = len(item.args.args)
                self.AddNode(func_node)
                self.AddEdge(Edge(py_node.id, func_id, "DEFINES"))
    def BuildImportEdges(self, py_nodes):
        path_to_id = {}
        for n in py_nodes:
            base = os.path.splitext(os.path.basename(n.path))[0]
            path_to_id[base] = n.id
        for py_node in py_nodes:
            if not os.path.exists(py_node.path):
                continue
            with open(py_node.path, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=py_node.path)
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module in path_to_id:
                        target_id = path_to_id[node.module]
                        if target_id != py_node.id:
                            self.AddEdge(Edge(py_node.id, target_id, "IMPORTS"))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in path_to_id:
                            target_id = path_to_id[alias.name]
                            if target_id != py_node.id:
                                self.AddEdge(Edge(py_node.id, target_id, "IMPORTS"))
        return (1, None, None)
    def DetectCycles(self):
        visited = set()
        stack = []
        cycles = []
        def DFS(node_id):
            if node_id in stack:
                idx = stack.index(node_id)
                cycles.append(stack[idx:] + [node_id])
                return (1, None, None)
            if node_id in visited:
                return (1, None, None)
            visited.add(node_id)
            stack.append(node_id)
            for neighbor in self.adj.get(node_id, []):
                DFS(neighbor)
            stack.pop()
        for node_id in self.nodes:
            if node_id not in visited:
                DFS(node_id)
        return (1, cycles, None)
    def FindPaths(self, start_id, max_depth=Config.MAX_DEPTH):
        paths = []
        def Walk(node_id, path, depth):
            if depth > max_depth:
                return (1, None, None)
            path.append(node_id)
            neighbors = self.adj.get(node_id, [])
            if not neighbors:
                paths.append(list(path))
            else:
                for nxt in neighbors:
                    if nxt not in path:
                        Walk(nxt, path, depth + 1)
            path.pop()
        Walk(start_id, [], 0)
        return (1, paths, None)
    def GetRoots(self):
        return (1, [nid for nid in self.nodes if not self.radj.get(nid)], None)
    def GetLeaves(self):
        return (1, [nid for nid in self.nodes if not self.adj.get(nid)], None)
    def GetHubs(self, threshold=Config.HUB_THRESHOLD):
        return (1, [(nid, len(self.adj.get(nid, [])))
                for nid in self.nodes
                if len(self.adj.get(nid, [])) >= threshold], None)
    def GetTypeCounts(self):
        counts = defaultdict(int)
        for node in self.nodes.values():
            counts[node.type] += 1
        return (1, dict(counts), None)
    def IsDAG(self):
        return (1, len(self.DetectCycles()) == 0, None)
    def GetComponents(self):
        visited = set()
        components = []
        for node_id in self.nodes:
            if node_id in visited:
                continue
            component = []
            queue = deque([node_id])
            while queue:
                nid = queue.popleft()
                if nid in visited:
                    continue
                visited.add(nid)
                component.append(nid)
                for neighbor in self.adj.get(nid, []):
                    queue.append(neighbor)
                for neighbor in self.radj.get(nid, []):
                    queue.append(neighbor)
            components.append(component)
        return (1, components, None)
    def Export(self):
        cycles = self.DetectCycles()
        return (1, {
            "primitives": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
            },
            "node_types": self.GetTypeCounts(),
            "nodes": [n.ToDict() for n in self.nodes.values()],
            "edges": [e.ToDict() for e in self.edges],
            "derived": {
                "cycles": cycles,
                "cycle_count": len(cycles),
                "is_dag": len(cycles) == 0,
                "roots": self.GetRoots(),
                "leaves": self.GetLeaves(),
                "hubs": self.GetHubs(Config.HUB_THRESHOLD),
                "components": self.GetComponents(),
                "component_count": len(self.GetComponents()),
            },
        }, None)
    def Run(self, command, params=None):
        dispatch = {
            'read_state': self.read_state,
            'set_config': self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params or {})
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
if __name__ == "__main__":
    graph = TypedGraph()
    graph.Build(ROOT)
    output = graph.Export()
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    for ntype, count in sorted(output['node_types'].items()):
        pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    pass  # VBStyle: no print
    if output['derived']['cycles']:
        pass  # VBStyle: no print
        for cycle in output['derived']['cycles']:
            short = [os.path.basename(c.split("::")[0]) + ("::" + c.split("::")[1] if "::" in c else "") for c in cycle]
            pass  # VBStyle: no print
    if output['derived']['hubs']:
        pass  # VBStyle: no print
        for hub_id, count in output['derived']['hubs']:
            pass  # VBStyle: no print
