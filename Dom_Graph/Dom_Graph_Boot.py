#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Execution Graph Validator + Self-Modifying Topology for MemUnit boot permutations. 7 layers: permutation space, dependency graph, runtime simulation, graph extraction, path scoring, self-healing, convergence. No #[@...] headers (uses old-style comment blocks). No Run dispatch. No Tuple3 returns. __init__ has no mem/db/param params. Uses Config_efl_brain import. Has hardcoded paths.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Fix __init__ signature. Remove hardcoded paths.>]}
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     execution_graph.py
# Domain:   Graph Analysis
# Authority: State-transition graph validator for MemUnit boot permutations
# DB:       None (pure computation)
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @hardcode — No hardcoded paths
#   @cstyle   — Coding style compliant
# ============================================================================
"""
Execution Graph Validator + Self-Modifying Topology
Layer 1: Permutation space — all valid execution orders
Layer 2: Dependency graph — constraint closure
Layer 3: Runtime simulation — failure state detection
Layer 4: Graph extraction — adjacency from real permutations
Layer 5: Weighted path scoring — stability score per boot path
Layer 6: Self-healing — failed paths auto-rewrite dependency edges
Layer 7: Convergence — iterate until stable boot topology found
"""
import ast
import os
import json
import hashlib
from itertools import permutations
from collections import defaultdict, deque
from typing import Any
import Config_efl_brain as Config
# ============================================================================
# CLASSES HEADER
# ----------------------------------------------------------------------------
# Class:  ExecutionGraph
# Domain: Graph Analysis
# Authority: Builds, validates, simulates, and heals execution graphs
# Dependencies: itertools, collections, ast, hashlib
# ============================================================================
class ExecutionGraph:
    """Directed state-transition graph for MemUnit boot permutations."""
    def __init__(self):
        self.state = {}
        self.state["nodes"] = []
        self.state["dependencies"] = {}
        self.state["runtime_rules"] = {}
        self.state["adjacency"] = defaultdict(list)
        self.state["path_scores"] = {}
        self.state["healed_edges"] = []
        self.state["iteration"] = 0
        self.state["converged"] = False
    def AddNode(self, name):
        """Register a system node (MemUnit, Config, etc.)."""
        if name not in self.state["nodes"]:
            self.state["nodes"].append(name)
            self.state["dependencies"][name] = []
        return (1, None, None)
    def AddDependency(self, node, depends_on):
        """Register a hard constraint: node must execute after depends_on."""
        if node not in self.state["dependencies"]:
            self.state["dependencies"][node] = []
        for dep in depends_on:
            if dep not in self.state["dependencies"][node]:
                self.state["dependencies"][node].append(dep)
        return (1, None, None)
    def AddRuntimeRule(self, node, rule_fn):
        """Register a runtime validation function for a node.
        rule_fn receives (state, node) and returns (ok, error)."""
        self.state["runtime_rules"][node] = rule_fn
        return (1, None, None)
    def IsValidOrder(self, order):
        """Check if a permutation respects all dependency constraints."""
        position = {node: i for i, node in enumerate(order)}
        for node, deps in self.state["dependencies"].items():
            for dep in deps:
                if node in position and dep in position:
                    if position[node] < position[dep]:
                        return (1, False, None)
        return (1, True, None)
    def ExecutePath(self, order):
        """Simulate runtime execution of a given node ordering.
        Returns (ok, log, state_snapshot)."""
        sim_state = {}
        log = []
        for node in order:
            rule = self.state["runtime_rules"].get(node)
            if rule:
                ok, error = rule(sim_state, node)
                if not ok:
                    log.append((node, "FAIL", error))
                    return False, log, sim_state
            sim_state[node] = "OK"
            log.append((node, "SUCCESS", ""))
        return True, log, sim_state
    def BuildGraph(self):
        """Generate all valid permutations, simulate each, yield results."""
        nodes = self.state["nodes"]
        if not nodes:
            return (1, None, None)
        for perm in permutations(nodes):
            if not self.IsValidOrder(perm):
                continue
            ok, log, sim_state = self.ExecutePath(perm)
            for i in range(len(perm) - 1):
                src = perm[i]
                dst = perm[i + 1]
                if dst not in self.state["adjacency"][src]:
                    self.state["adjacency"][src].append(dst)
            yield {
                "order": perm,
                "success": ok,
                "log": log,
                "state": dict(sim_state),
            }
    def ScorePath(self, order, success, log):
        """Calculate stability score for a boot path.
        Score factors:
          - Success: +100
          - Early failure: penalty proportional to position
          - Dependency depth: deeper = more fragile
          - Edge diversity: more unique edges = more flexible
        """
        score = 0
        if success:
            score += 100
            depth = 0
            for node in order:
                deps = self.state["dependencies"].get(node, [])
                depth += len(deps)
            score -= depth * 2
            unique_edges = 0
            for i in range(len(order) - 1):
                src = order[i]
                dst = order[i + 1]
                if dst in self.state["adjacency"].get(src, []):
                    unique_edges += 1
            score += unique_edges * 5
        else:
            fail_pos = 0
            for i, (node, status, _) in enumerate(log):
                if status == "FAIL":
                    fail_pos = i
                    break
            score = -(50 + fail_pos * 10)
        return (1, score, None)
    def HealFailedPaths(self, results):
        """For each failed path, attempt to rewrite dependency edges
        so the path becomes valid. Track healed edges."""
        healed = []
        for result in results:
            if result["success"]:
                continue
            order = result["order"]
            log = result["log"]
            for i, (node, status, error) in enumerate(log):
                if status != "FAIL":
                    continue
                deps = self.state["dependencies"].get(node, [])
                for j, dep in enumerate(order[:i]):
                    if dep not in deps:
                        deps.append(dep)
                        healed.append({
                            "node": node,
                            "added_dep": dep,
                            "reason": error,
                            "iteration": self.state["iteration"],
                        })
                self.state["dependencies"][node] = deps
                break
        self.state["healed_edges"].extend(healed)
        return (1, healed, None)
    def Converge(self, max_iterations=Config.MAX_DEPTH):
        """Iterate: build graph, score paths, heal failures, repeat.
        Stops when all valid paths succeed or max iterations reached."""
        history = []
        for iteration in range(max_iterations):
            self.state["iteration"] = iteration
            results = list(self.BuildGraph())
            if not results:
                history.append({
                    "iteration": iteration,
                    "total": 0,
                    "success": 0,
                    "fail": 0,
                    "healed": 0,
                    "converged": True,
                })
                self.state["converged"] = True
                break
            success_count = sum(1 for r in results if r["success"])
            fail_count = len(results) - success_count
            for r in results:
                score = self.ScorePath(r["order"], r["success"], r["log"])
                self.state["path_scores"][str(r["order"])] = score
            healed = self.HealFailedPaths(results)
            history.append({
                "iteration": iteration,
                "total": len(results),
                "success": success_count,
                "fail": fail_count,
                "healed": len(healed),
                "converged": fail_count == 0,
            })
            if fail_count == 0:
                self.state["converged"] = True
                break
        return (1, history, None)
    def DetectCycles(self):
        """Detect cycles in the adjacency graph using DFS."""
        visited = set()
        stack = set()
        cycles = []
        def Visit(node, path):
            if node in stack:
                cycle_start = path.index(node) if node in path else 0
                cycles.append(path[cycle_start:] + [node])
                return (1, None, None)
            if node in visited:
                return (1, None, None)
            visited.add(node)
            stack.add(node)
            for neighbor in self.state["adjacency"].get(node, []):
                Visit(neighbor, path + [node])
            stack.discard(node)
        for node in self.state["nodes"]:
            if node not in visited:
                Visit(node, [])
        return (1, cycles, None)
    def DetectDeadStates(self):
        """Find nodes that appear in no successful path."""
        successful_nodes = set()
        for result in self.BuildGraph():
            if result["success"]:
                for node in result["order"]:
                    successful_nodes.add(node)
        all_nodes = set(self.state["nodes"])
        return (1, all_nodes - successful_nodes, None)
    def DetectUnreachable(self):
        """Find nodes that no edge points to (no incoming edges)."""
        all_targets = set()
        for src, targets in self.state["adjacency"].items():
            all_targets.update(targets)
        all_nodes = set(self.state["nodes"])
        roots = [n for n in self.state["nodes"] if n not in all_targets]
        reachable = set()
        queue = deque(roots)
        while queue:
            node = queue.popleft()
            if node in reachable:
                continue
            reachable.add(node)
            for neighbor in self.state["adjacency"].get(node, []):
                queue.append(neighbor)
        return (1, all_nodes - reachable, None)
    def GetBestPaths(self, top_n=5):
        """Return the highest-scoring boot paths."""
        scored = sorted(
            self.state["path_scores"].items(),
            key=lambda x: x[1],
            reverse=True
        )
        return (1, [
            {"order": eval(k), "score": v}
            for k, v in scored[:top_n]
        ], None)
    def GenerateReport(self):
        """Generate full analysis report as dict."""
        results = list(self.BuildGraph())
        success = [r for r in results if r["success"]]
        fail = [r for r in results if not r["success"]]
        return (1, {
            "nodes": self.state["nodes"],
            "dependencies": dict(self.state["dependencies"]),
            "adjacency": dict(self.state["adjacency"]),
            "total_valid_paths": len(results),
            "successful_paths": len(success),
            "failed_paths": len(fail),
            "cycles": self.DetectCycles(),
            "dead_states": list(self.DetectDeadStates()),
            "unreachable": list(self.DetectUnreachable()),
            "best_paths": self.GetBestPaths(5),
            "healed_edges": self.state["healed_edges"],
            "converged": self.state["converged"],
            "iterations": self.state["iteration"],
        }, None)
    def ScanFolder(self, folder_path):
        """Scan a folder of Python files and build dependency graph from imports."""
        files = [f for f in os.listdir(folder_path) if f.endswith(".py")]
        module_names = {}
        for f in files:
            mod_name = f.replace(".py", "")
            module_names[mod_name] = f
            self.AddNode(mod_name)
        for f in files:
            mod_name = f.replace(".py", "")
            file_path = os.path.join(folder_path, f)
            with open(file_path, "r") as fh:
                try:
                    tree = ast.parse(fh.read())
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module in module_names:
                        self.AddDependency(mod_name, [node.module])
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in module_names:
                            self.AddDependency(mod_name, [alias.name])
        return (1, None, None)
    def HashFiles(self, folder_path):
        """Compute SHA256 for all Python files in folder."""
        hashes = {}
        for f in os.listdir(folder_path):
            if f.endswith(".py"):
                file_path = os.path.join(folder_path, f)
                with open(file_path, "rb") as fh:
                    hashes[f] = hashlib.sha256(fh.read()).hexdigest()
        return (1, hashes, None)
    def Run(self, command, params):
        """Dispatch entry point — returns Tuple3 (ok, data, error)."""
        DISPATCH = {
            "analyze": self.RunAnalyze,
            "converge": self.RunConverge,
            "scan": self.RunScan,
            "report": self.RunReport,
            "cycles": self.RunCycles,
            "dead": self.RunDead,
            "unreachable": self.RunUnreachable,
            "best": self.RunBest,
            "hashes": self.RunHashes,
        }
        handler = DISPATCH.get(command)
        if handler is None:
            return (False, None, f"Unknown command: {command}")
        return handler(params)
    def RunAnalyze(self, params):
        """Run full analysis without convergence."""
        report = self.GenerateReport()
        return (True, report, "")
    def RunConverge(self, params):
        """Run convergence analysis with self-healing."""
        max_iter = params.get("max_iterations", Config.MAX_DEPTH) if params else Config.MAX_DEPTH
        history = self.Converge(max_iter)
        report = self.GenerateReport()
        report["convergence_history"] = history
        return (True, report, "")
    def RunScan(self, params):
        """Scan a folder and build dependency graph from imports."""
        folder = params.get("folder", "") if params else ""
        if not folder or not os.path.isdir(folder):
            return (False, None, "Invalid folder path")
        self.ScanFolder(folder)
        return (True, {"nodes": self.state["nodes"], "deps": dict(self.state["dependencies"])}, "")
    def RunReport(self, params):
        """Generate full report."""
        report = self.GenerateReport()
        return (True, report, "")
    def RunCycles(self, params):
        """Detect cycles only."""
        cycles = self.DetectCycles()
        return (True, {"cycles": cycles, "count": len(cycles)}, "")
    def RunDead(self, params):
        """Detect dead states only."""
        dead = self.DetectDeadStates()
        return (True, {"dead_states": list(dead), "count": len(dead)}, "")
    def RunUnreachable(self, params):
        """Detect unreachable nodes only."""
        unreachable = self.DetectUnreachable()
        return (True, {"unreachable": list(unreachable), "count": len(unreachable)}, "")
    def RunBest(self, params):
        """Get best-scoring paths only."""
        top_n = params.get("top_n", 5) if params else 5
        best = self.GetBestPaths(top_n)
        return (True, {"best_paths": best}, "")
    def RunHashes(self, params):
        """Compute file hashes for a folder."""
        folder = params.get("folder", "") if params else ""
        if not folder or not os.path.isdir(folder):
            return (False, None, "Invalid folder path")
        hashes = self.HashFiles(folder)
        return (True, hashes, "")
def DemoConfigArchitecture():
    """Demo: Config architecture convergence."""
    def ConfigRule(state, node):
        if node != "Config":
            return (False, "Rule mismatch")
        return (True, "")
    def MemUnitRule(state, node):
        if "Config" not in state:
            return (False, "MemUnit boot failure: missing Config")
        return (True, "")
    def MySQLRule(state, node):
        if "MemUnit" not in state:
            return (False, "MySQL missing MemUnit context")
        return (True, "")
    def VectorDBRule(state, node):
        if "MemUnit" not in state:
            return (False, "VectorDB missing MemUnit context")
        return (True, "")
    def EventBusRule(state, node):
        if "Config" not in state:
            return (False, "EventBus missing Config")
        return (True, "")
    def AgentCoreRule(state, node):
        if "MemUnit" not in state:
            return (False, "AgentCore missing MemUnit")
        if "EventBus" not in state:
            return (False, "AgentCore missing EventBus")
        return (True, "")
    graph.AddRuntimeRule("Config", ConfigRule)
    graph.AddRuntimeRule("MemUnit", MemUnitRule)
    graph.AddRuntimeRule("MySQLConn", MySQLRule)
    graph.AddRuntimeRule("VectorDB", VectorDBRule)
    graph.AddRuntimeRule("EventBus", EventBusRule)
    graph.AddRuntimeRule("AgentCore", AgentCoreRule)
    # Run convergence
    ok, data, err = graph.Run("converge", {"max_iterations": 5})
    if not ok:
        pass
        return
    pass
    pass
    pass
    pass
    if data["cycles"]:
        pass
        for cycle in data["cycles"]:
            pass
    else:
        pass
    if data["dead_states"]:
        pass
    else:
        pass
    if data["unreachable"]:
        pass
    else:
        pass
    if data["healed_edges"]:
        pass
        for edge in data["healed_edges"][:5]:
            pass
    else:
        pass
    for i, path in enumerate(data["best_paths"], 1):
        pass
    for src, targets in data["adjacency"].items():
        pass
    if "convergence_history" in data:
        pass
        for h in data["convergence_history"]:
            status = "CONVERGED" if h["converged"] else "NOT CONVERGED"
    return data
# ============================================================================
# FOLDER SCAN DEMO — scan real workspace folder
# ============================================================================
def DemoFolderScan(folder_path):
    """Scan a real folder and analyze its import graph."""
    pass
    graph = ExecutionGraph()
    ok, data, err = graph.Run("scan", {"folder": folder_path})
    if not ok:
        pass
        return
    pass
    for node, deps in data["deps"].items():
        if deps:
            pass
        else:
            pass
    ok, cycles, err = graph.Run("cycles", None)
    if cycles["count"] > 0:
        pass
        for cycle in cycles["cycles"]:
            pass
    else:
        pass
    ok, dead, err = graph.Run("dead", None)
    ok, unreachable, err = graph.Run("unreachable", None)
    ok, hashes, err = graph.Run("hashes", {"folder": folder_path})
    if ok:
        pass
        for fname, h in hashes.items():
            pass
# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    # Run config architecture demo
    DemoConfigArchitecture()
    # If a folder argument is provided, scan it
    if len(os.sys.argv) > 1:
        folder = os.sys.argv[1]
        if os.path.isdir(folder):
            DemoFolderScan(folder)
        else:
            pass

