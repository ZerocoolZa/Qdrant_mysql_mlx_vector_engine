# [@GHOST]
# Ghost header — GraphEngine
# Purpose: Graph views + algorithms executor. GATED by CascadeEngine.
# Layer: Below GraphOrchestrator. Above GraphViewer and 8 Views.
# Triangle: Cascade validates -> GraphEngine executes -> DEGS evolves
# [@VBSTYLE]
# VBStyle: Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE
# Rules: @ghost(33), @vbsty(34), @cstyle(35), @clshdr(36), @mthdr(37), @pascal(38), @upper(39), @print(22), @decorators(20), @hardcode(24), @underscore(19), @run(43), @t3(50), @state(41), @ctor(40), @memunit(32), @dismap(31)

import os
import sys
import sqlite3
from Config_graph_engine import cfg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Inspect import Inspect
from Verify import Verify


class GraphEngine:
    """Graph executor. All graph views, algorithms, search. GATED by cascade."""

    def __init__(self):
        self.state = {
            "db_path": cfg.DB_PATH,
            "domain": cfg.DOMAIN,
            "inspect": Inspect(),
            "verify": Verify(),
            "cascade_run_id": None,
        }

    def Run(self, command, params):
        """Dispatch entry point. Returns Tuple3(ok, data, error)."""
        if params is None:
            params = {}
        dispatch = {
            "plan": self.PlanView,
            "spec": self.SpecView,
            "flow": self.FlowView,
            "lifecycle": self.LifecycleView,
            "dependency": self.DependencyView,
            "error": self.ErrorView,
            "orchestration": self.OrchestrationView,
            "gap": self.GapView,
            "inspect": self.InspectCmd,
            "verify": self.VerifyCmd,
            "bfs": self.Bfs,
            "dfs": self.Dfs,
            "cycle": self.Cycle,
            "path": self.Path,
            "topology": self.Topology,
            "search": self.Search,
            "instructions": self.Instructions,
            "code": self.Code,
            "remove_class": self.RemoveClass,
            "add_class": self.AddClass,
            "status": self.Status,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, "unknown_command: {command}".format(command=command))
        return handler(params)

    def _GetDb(self):
        return sqlite3.connect(self.state["db_path"])

    def PlanView(self, params):
        """Return plan graph data — capabilities from spec_data or plans table."""
        domain = params.get("domain", self.state["domain"])
        db = self._GetDb()
        cur = db.cursor()
        rows = cur.execute(
            "SELECT sequence, step_name, description FROM plan_steps WHERE domain=? ORDER BY sequence",
            (domain,),
        ).fetchall()
        db.close()
        steps = [{"step": r[0], "name": r[1], "desc": r[2]} for r in rows]
        if not steps:
            rows = cur.execute(
                "SELECT sequence, step_name, description FROM plan_steps ORDER BY sequence LIMIT 20",
            ).fetchall()
            steps = [{"step": r[0], "name": r[1], "desc": r[2]} for r in rows]
        return (1, {"view": "plan", "domain": domain, "steps": steps, "count": len(steps)}, None)

    def SpecView(self, params):
        """Return spec graph data — classes and methods."""
        domain = params.get("domain", self.state["domain"])
        db = self._GetDb()
        cur = db.cursor()
        classes = cur.execute(
            "SELECT class_name, is_vbstyle FROM classes WHERE domain=? ORDER BY class_name",
            (domain,),
        ).fetchall()
        db.close()
        cls_list = [{"name": r[0], "vbstyle": r[1]} for r in classes]
        return (1, {"view": "spec", "domain": domain, "classes": cls_list, "count": len(cls_list)}, None)

    def FlowView(self, params):
        """Return flow graph data — execution paths from orchestration table."""
        domain = params.get("domain", self.state["domain"])
        db = self._GetDb()
        cur = db.cursor()
        flows = cur.execute(
            "SELECT role, description, pipeline FROM orchestration ORDER BY sequence",
        ).fetchall()
        db.close()
        flow_list = [{"role": r[0], "description": r[1], "pipeline": r[2]} for r in flows]
        return (1, {"view": "flow", "domain": domain, "flows": flow_list, "count": len(flow_list)}, None)

    def LifecycleView(self, params):
        """Return lifecycle graph data — temporal phases."""
        domain = params.get("domain", self.state["domain"])
        phases = [
            {"phase": "ingest", "order": 1, "actions": ["read_files", "parse_ast", "insert_classes"]},
            {"phase": "validate", "order": 2, "actions": ["cascade_validate", "check_rules"]},
            {"phase": "execute", "order": 3, "actions": ["degs_start", "degs_step", "degs_auto"]},
            {"phase": "verify", "order": 4, "actions": ["verify_all", "verify_report"]},
            {"phase": "evolve", "order": 5, "actions": ["auto_generate", "dedup", "promote", "prune"]},
            {"phase": "cleanup", "order": 6, "actions": ["end_run", "write_metrics", "clean_tmp"]},
        ]
        return (1, {"view": "lifecycle", "domain": domain, "phases": phases, "count": len(phases)}, None)

    def DependencyView(self, params):
        """Return dependency graph data — edge justifications."""
        domain = params.get("domain", self.state["domain"])
        deps = [
            {"from": "GraphOrchestrator", "to": "GraphEngine", "reason": "coordinates"},
            {"from": "GraphOrchestrator", "to": "DecisionEngine", "reason": "coordinates"},
            {"from": "GraphOrchestrator", "to": "TmpWorkspace", "reason": "coordinates"},
            {"from": "GraphOrchestrator", "to": "CascadeEngine", "reason": "coordinates"},
            {"from": "GraphEngine", "to": "Inspect", "reason": "uses"},
            {"from": "GraphEngine", "to": "Verify", "reason": "uses"},
            {"from": "DecisionEngine", "to": "AutoGenerator", "reason": "uses"},
            {"from": "DecisionEngine", "to": "bcl_instructions", "reason": "reads"},
            {"from": "AutoGenerator", "to": "execution_log", "reason": "reads"},
        ]
        return (1, {"view": "dependency", "domain": domain, "dependencies": deps, "count": len(deps)}, None)

    def ErrorView(self, params):
        """Return error graph data — failure modes and recovery."""
        errors = [
            {"error": "SyntaxError", "detection": "py_compile", "recovery": "fix_and_rerun"},
            {"error": "Missing Run()", "detection": "VerifyRunner", "recovery": "add_run_or_mark"},
            {"error": "Missing Tuple3", "detection": "VerifyRunner", "recovery": "refactor_returns"},
            {"error": "Hardcoded path", "detection": "VerifyRunner", "recovery": "use_config"},
            {"error": "ImportError", "detection": "runtime", "recovery": "search_or_stub"},
            {"error": "VBStyle violation", "detection": "VerifyRunner", "recovery": "fix_or_resolve"},
            {"error": "Terminal node", "detection": "step()", "recovery": "complete_run"},
            {"error": "Deleted node", "detection": "step()", "recovery": "fail_run"},
            {"error": "BCL not found", "detection": "parser", "recovery": "fallback_edge"},
            {"error": "Tkinter fail", "detection": "try/except", "recovery": "headless"},
            {"error": "Duplicate fallback", "detection": "dedup", "recovery": "skip"},
            {"error": "Concurrent write", "detection": "BEGIN IMMEDIATE", "recovery": "retry"},
            {"error": "Max retry", "detection": "loop_count", "recovery": "pause"},
            {"error": "Max steps", "detection": "step counter", "recovery": "pause"},
            {"error": "Permission denied", "detection": "AmIAllowed", "recovery": "log"},
            {"error": "Stale run", "detection": "1hr timeout", "recovery": "auto_cleanup"},
        ]
        return (1, {"view": "error", "errors": errors, "count": len(errors)}, None)

    def OrchestrationView(self, params):
        """Return orchestration graph data — call tree."""
        calls = [
            {"caller": "User/AI", "callee": "GraphOrchestrator.Run()", "type": "root"},
            {"caller": "GraphOrchestrator", "callee": "CascadeEngine.Run()", "type": "forward"},
            {"caller": "GraphOrchestrator", "callee": "GraphEngine.Run()", "type": "forward"},
            {"caller": "GraphOrchestrator", "callee": "DecisionEngine.Run()", "type": "forward"},
            {"caller": "GraphOrchestrator", "callee": "TmpWorkspace.Run()", "type": "forward"},
            {"caller": "GraphEngine", "callee": "Inspect.Run()", "type": "dispatch"},
            {"caller": "GraphEngine", "callee": "Verify.Run()", "type": "dispatch"},
            {"caller": "DecisionEngine", "callee": "AutoGenerator.Run()", "type": "dispatch"},
        ]
        return (1, {"view": "orchestration", "calls": calls, "count": len(calls)}, None)

    def GapView(self, params):
        """Return gap graph data — missing pairs, CRUD closure."""
        domain = params.get("domain", self.state["domain"])
        db = self._GetDb()
        cur = db.cursor()
        tables = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('cascade_runs','cascade_stage_results','cascade_rules','decision_nodes','decision_edges','execution_log','run_state','run_metrics','spec_data') ORDER BY name"
        ).fetchall()
        existing = {r[0] for r in tables}
        expected = {"cascade_runs", "cascade_stage_results", "cascade_rules", "decision_nodes", "decision_edges", "execution_log", "run_state", "run_metrics", "spec_data"}
        missing = list(expected - existing)
        db.close()
        return (1, {"view": "gap", "domain": domain, "existing_tables": list(existing), "missing_tables": missing, "missing_count": len(missing)}, None)

    def InspectCmd(self, params):
        """Forward to Inspect MemUnit."""
        sub_cmd = params.get("sub_command", "parse")
        return self.state["inspect"].Run(sub_cmd, params)

    def VerifyCmd(self, params):
        """Forward to Verify MemUnit."""
        sub_cmd = params.get("sub_command", "all")
        return self.state["verify"].Run(sub_cmd, params)

    def Bfs(self, params):
        """BFS traversal on decision_edges."""
        start = params.get("start_node")
        if not start:
            return (0, None, "missing_param: start_node")
        db = self._GetDb()
        cur = db.cursor()
        visited = set()
        queue = [start]
        order = []
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            order.append(node)
            children = cur.execute(
                "SELECT to_node FROM decision_edges WHERE from_node=?", (node,)
            ).fetchall()
            for child in children:
                if child[0] not in visited:
                    queue.append(child[0])
        db.close()
        return (1, {"traversal": "bfs", "start": start, "order": order, "visited": len(visited)}, None)

    def Dfs(self, params):
        """DFS traversal on decision_edges."""
        start = params.get("start_node")
        if not start:
            return (0, None, "missing_param: start_node")
        db = self._GetDb()
        cur = db.cursor()
        visited = set()
        order = []
        def DfsRecursive(node):
            if node in visited:
                return
            visited.add(node)
            order.append(node)
            children = cur.execute(
                "SELECT to_node FROM decision_edges WHERE from_node=?", (node,)
            ).fetchall()
            for child in children:
                DfsRecursive(child[0])
        DfsRecursive(start)
        db.close()
        return (1, {"traversal": "dfs", "start": start, "order": order, "visited": len(visited)}, None)

    def Cycle(self, params):
        """Detect cycles in decision_edges using DFS."""
        db = self._GetDb()
        cur = db.cursor()
        nodes = cur.execute("SELECT DISTINCT from_node FROM decision_edges").fetchall()
        visited = set()
        rec_stack = set()
        cycles = []
        def DetectCycle(node):
            visited.add(node)
            rec_stack.add(node)
            children = cur.execute(
                "SELECT to_node FROM decision_edges WHERE from_node=?", (node,)
            ).fetchall()
            for child in children:
                c = child[0]
                if c not in visited:
                    DetectCycle(c)
                elif c in rec_stack:
                    cycles.append((node, c))
            rec_stack.discard(node)
        for n in nodes:
            if n[0] not in visited:
                DetectCycle(n[0])
        db.close()
        return (1, {"has_cycles": len(cycles) > 0, "cycles": cycles, "count": len(cycles)}, None)

    def Path(self, params):
        """Find path between two nodes."""
        start = params.get("start_node")
        end = params.get("end_node")
        if not start or not end:
            return (0, None, "missing_param: start_node and end_node")
        db = self._GetDb()
        cur = db.cursor()
        visited = set()
        def FindPath(node, target, path):
            if node in visited:
                return None
            visited.add(node)
            if node == target:
                return path + [node]
            children = cur.execute(
                "SELECT to_node FROM decision_edges WHERE from_node=?", (node,)
            ).fetchall()
            for child in children:
                result = FindPath(child[0], target, path + [node])
                if result:
                    return result
            return None
        found = FindPath(start, end, [])
        db.close()
        return (1, {"start": start, "end": end, "path": found, "found": found is not None}, None)

    def Topology(self, params):
        """Topological sort of decision_edges."""
        db = self._GetDb()
        cur = db.cursor()
        nodes = {r[0] for r in cur.execute("SELECT DISTINCT from_node FROM decision_edges").fetchall()}
        nodes.update({r[0] for r in cur.execute("SELECT DISTINCT to_node FROM decision_edges").fetchall()})
        in_degree = {n: 0 for n in nodes}
        for n in nodes:
            children = cur.execute("SELECT to_node FROM decision_edges WHERE from_node=?", (n,)).fetchall()
            for c in children:
                in_degree[c[0]] = in_degree.get(c[0], 0) + 1
        queue = [n for n in nodes if in_degree[n] == 0]
        order = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            children = cur.execute("SELECT to_node FROM decision_edges WHERE from_node=?", (node,)).fetchall()
            for c in children:
                in_degree[c[0]] -= 1
                if in_degree[c[0]] == 0:
                    queue.append(c[0])
        db.close()
        return (1, {"topology": order, "count": len(order)}, None)

    def Search(self, params):
        """FTS5 search in DB."""
        query = params.get("query")
        if not query:
            return (0, None, "missing_param: query")
        db = self._GetDb()
        cur = db.cursor()
        try:
            results = cur.execute(
                "SELECT class_name, snippet(search_idx, 1, '[', ']', '...', 10) FROM search_idx WHERE search_idx MATCH ? LIMIT 20",
                (query,),
            ).fetchall()
            search_results = [{"class": r[0], "snippet": r[1]} for r in results]
        except Exception as exc:
            db.close()
            return (0, None, "search_error: {msg}".format(msg=str(exc)))
        db.close()
        return (1, {"query": query, "results": search_results, "count": len(search_results)}, None)

    def Instructions(self, params):
        """Return BCL instructions from DB."""
        db = self._GetDb()
        cur = db.cursor()
        rows = cur.execute(
            "SELECT token_name, bcl_content, category FROM bcl_instructions ORDER BY token_name"
        ).fetchall()
        db.close()
        instructions = [{"name": r[0], "body": r[1], "category": r[2]} for r in rows]
        return (1, {"instructions": instructions, "count": len(instructions)}, None)

    def Code(self, params):
        """HARD GATE: only allowed if cascade_runs.status == 'passed'."""
        cascade_run_id = params.get("cascade_run_id", self.state.get("cascade_run_id"))
        if not cascade_run_id:
            return (0, None, cfg.GetError("cascade_not_passed"))
        db = self._GetDb()
        cur = db.cursor()
        row = cur.execute(
            "SELECT status FROM cascade_runs WHERE run_id=?", (cascade_run_id,)
        ).fetchone()
        db.close()
        if not row or row[0] != "passed":
            return (0, None, cfg.GetError("cascade_not_passed"))
        action = params.get("action", "generate")
        return (1, {"action": action, "cascade_run_id": cascade_run_id, "allowed": True}, None)

    def RemoveClass(self, params):
        """Remove a class from the DB."""
        class_id = params.get("class_id")
        class_name = params.get("class_name")
        if not class_id and not class_name:
            return (0, None, "missing_param: class_id or class_name")
        db = self._GetDb()
        cur = db.cursor()
        if class_name:
            cur.execute("DELETE FROM classes WHERE class_name=? AND domain=?", (class_name, self.state["domain"]))
        else:
            cur.execute("DELETE FROM classes WHERE id=?", (class_id,))
        removed = cur.rowcount
        db.commit()
        db.close()
        return (1, {"removed": removed, "class_name": class_name}, None)

    def AddClass(self, params):
        """Add a class to the DB."""
        class_name = params.get("class_name")
        class_code = params.get("class_code", "")
        if not class_name:
            return (0, None, "missing_param: class_name")
        db = self._GetDb()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO classes (domain, class_name, class_code, is_vbstyle) VALUES (?, ?, ?, ?)",
            (self.state["domain"], class_name, class_code, 1),
        )
        new_id = cur.lastrowid
        db.commit()
        db.close()
        return (1, {"class_id": new_id, "class_name": class_name, "added": True}, None)

    def Status(self, params):
        """Return engine status."""
        db = self._GetDb()
        cur = db.cursor()
        class_count = cur.execute(
            "SELECT COUNT(*) FROM classes WHERE domain=?", (self.state["domain"],)
        ).fetchone()[0]
        node_count = cur.execute("SELECT COUNT(*) FROM decision_nodes").fetchone()[0]
        edge_count = cur.execute("SELECT COUNT(*) FROM decision_edges").fetchone()[0]
        db.close()
        return (
            1,
            {
                "domain": self.state["domain"],
                "classes": class_count,
                "decision_nodes": node_count,
                "decision_edges": edge_count,
                "cascade_run_id": self.state.get("cascade_run_id"),
            },
            None,
        )
