# [@GHOST]
# Ghost header — DecisionEngine
# Purpose: DEGS decision graph execution. ACT -> VERIFY -> BRANCH -> LOG -> REPEAT
# Layer: Sits below GraphOrchestrator. Evolves structure via AutoGenerator.
# [@VBSTYLE]
# VBStyle: Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE
# Rules: @ghost(33), @vbsty(34), @cstyle(35), @clshdr(36), @mthdr(37), @pascal(38), @upper(39), @print(22), @decorators(20), @hardcode(24), @underscore(19), @run(43), @t3(50), @state(41), @ctor(40), @memunit(32), @dismap(31)

import os
import sys
import json
import time
import uuid
import sqlite3
from Config_graph_engine import cfg


class DecisionEngine:
    """DEGS execution engine. Walks decision graph, logs every step."""

    def __init__(self):
        self.state = {
            "db_path": cfg.DB_PATH,
            "run_id": None,
            "current_node": None,
            "step_count": 0,
            "loop_count": 0,
            "start_time": None,
        }

    def Run(self, command, params):
        """Dispatch entry point. Returns Tuple3(ok, data, error)."""
        if params is None:
            params = {}
        dispatch = {
            "start": self.Start,
            "step": self.Step,
            "auto": self.Auto,
            "end": self.End,
            "get_node": self.GetNode,
            "get_edges": self.GetEdges,
            "log": self.Log,
            "status": self.Status,
            "history": self.History,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, "unknown_command: {command}".format(command=command))
        return handler(params)

    def Start(self, params):
        """Create run_id, initialize run_state, return run_id."""
        start_node = params.get("start_node", 1)
        run_id = "degs_" + uuid.uuid4().hex[:12]
        self.state["run_id"] = run_id
        self.state["current_node"] = start_node
        self.state["step_count"] = 0
        self.state["start_time"] = time.time()
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        node = cur.execute(
            "SELECT node_id FROM decision_nodes WHERE node_id=?", (start_node,)
        ).fetchone()
        if not node:
            db.close()
            return (0, None, "start_node_not_found: {nid}".format(nid=start_node))
        cur.execute(
            "INSERT INTO run_state (run_id, current_node, state) VALUES (?, ?, ?)",
            (run_id, start_node, "running"),
        )
        db.commit()
        db.close()
        return (1, {"run_id": run_id, "start_node": start_node, "state": "running"}, None)

    def Step(self, params):
        """Execute current node, branch to next. Returns node result."""
        run_id = params.get("run_id", self.state.get("run_id"))
        if not run_id:
            return (0, None, "missing_param: run_id")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        row = cur.execute(
            "SELECT current_node, state FROM run_state WHERE run_id=?", (run_id,)
        ).fetchone()
        if not row:
            db.close()
            return (0, None, "run_not_found: {rid}".format(rid=run_id))
        current_node, run_state = row
        if run_state in ("completed", "failed", "paused"):
            db.close()
            return (0, None, "run_not_active: state={state}".format(state=run_state))
        node = cur.execute(
            "SELECT node_id, name, node_type, payload FROM decision_nodes WHERE node_id=?",
            (current_node,),
        ).fetchone()
        if not node:
            cur.execute(
                "UPDATE run_state SET state='failed' WHERE run_id=?", (run_id,)
            )
            db.commit()
            db.close()
            return (0, None, cfg.GetError("current_node_deleted"))
        node_id, name, node_type, payload = node
        result = self.ExecuteNode(node_id, name, node_type, payload, cur, run_id)
        edges = cur.execute(
            "SELECT to_node, condition, weight FROM decision_edges WHERE from_node=? ORDER BY weight DESC",
            (node_id,),
        ).fetchall()
        if not edges:
            self.WriteLog(cur, run_id, node_id, "executed", json.dumps({"terminal": True}))
            cur.execute(
                "UPDATE run_state SET state='completed', updated_at=CURRENT_TIMESTAMP WHERE run_id=?",
                (run_id,),
            )
            db.commit()
            db.close()
            return (1, {"node": name, "result": result, "terminal": True, "state": "completed"}, None)
        next_node = None
        for to_node, condition, weight in edges:
            if self.MatchesCondition(condition, result):
                next_node = to_node
                break
        if next_node is None:
            fallback = cur.execute(
                "SELECT to_node FROM decision_edges WHERE from_node=? AND condition='error' ORDER BY weight DESC",
                (node_id,),
            ).fetchone()
            if fallback:
                next_node = fallback[0]
                self.WriteLog(cur, run_id, node_id, "fallback", json.dumps({"to": next_node}))
            else:
                cur.execute(
                    "UPDATE run_state SET state='failed', updated_at=CURRENT_TIMESTAMP WHERE run_id=?",
                    (run_id,),
                )
                db.commit()
                db.close()
                return (0, {"node": name, "result": result}, "no_matching_edge")
        cur.execute(
            "UPDATE run_state SET current_node=?, updated_at=CURRENT_TIMESTAMP WHERE run_id=?",
            (next_node, run_id),
        )
        db.commit()
        db.close()
        self.state["step_count"] += 1
        return (
            1,
            {
                "node": name,
                "node_type": node_type,
                "result": result,
                "next_node": next_node,
                "step": self.state["step_count"],
            },
            None,
        )

    def Auto(self, params):
        """Run to completion or max_steps."""
        run_id = params.get("run_id", self.state.get("run_id"))
        if not run_id:
            return (0, None, "missing_param: run_id")
        max_steps = params.get("max_steps", cfg.MAX_STEPS)
        steps_taken = 0
        results = []
        while steps_taken < max_steps:
            ok, data, err = self.Step({"run_id": run_id})
            steps_taken += 1
            if not ok:
                return (0, {"steps": steps_taken, "results": results}, err)
            results.append(data)
            if data.get("terminal") or data.get("state") == "completed":
                return (1, {"steps": steps_taken, "results": results, "state": "completed"}, None)
            if data.get("state") == "failed":
                return (0, {"steps": steps_taken, "results": results}, "run_failed")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        cur.execute(
            "UPDATE run_state SET state='paused', updated_at=CURRENT_TIMESTAMP WHERE run_id=?",
            (run_id,),
        )
        db.commit()
        db.close()
        return (0, {"steps": steps_taken, "results": results}, cfg.GetError("max_steps_exceeded"))

    def End(self, params):
        """End run, clean up run_state, write run_metrics."""
        run_id = params.get("run_id", self.state.get("run_id"))
        if not run_id:
            return (0, None, "missing_param: run_id")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        row = cur.execute(
            "SELECT current_node, state FROM run_state WHERE run_id=?", (run_id,)
        ).fetchone()
        if not row:
            db.close()
            return (0, None, "run_not_found: {rid}".format(rid=run_id))
        current_node, run_state = row
        final_state = "completed" if run_state != "failed" else "failed"
        log_count = cur.execute(
            "SELECT COUNT(*) FROM execution_log WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        fail_count = cur.execute(
            "SELECT COUNT(*) FROM execution_log WHERE run_id=? AND status='failed'",
            (run_id,),
        ).fetchone()[0]
        duration = time.time() - (self.state["start_time"] or time.time())
        success = 1 if final_state == "completed" else 0
        cur.execute(
            "UPDATE run_state SET state=?, updated_at=CURRENT_TIMESTAMP WHERE run_id=?",
            (final_state, run_id),
        )
        cur.execute(
            "INSERT INTO run_metrics (run_id, domain, total_nodes, nodes_executed, nodes_failed, fallbacks_created, duration_seconds, success) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, cfg.DOMAIN, 0, log_count, fail_count, 0, duration, success),
        )
        db.commit()
        db.close()
        return (
            1,
            {
                "run_id": run_id,
                "state": final_state,
                "nodes_executed": log_count,
                "nodes_failed": fail_count,
                "duration": round(duration, 2),
                "success": success,
            },
            None,
        )

    def GetNode(self, params):
        """Return node data."""
        node_id = params.get("node_id")
        if not node_id:
            return (0, None, "missing_param: node_id")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        node = cur.execute(
            "SELECT node_id, domain, name, node_type, payload, created_at FROM decision_nodes WHERE node_id=?",
            (node_id,),
        ).fetchone()
        db.close()
        if not node:
            return (0, None, "node_not_found: {nid}".format(nid=node_id))
        return (
            1,
            {
                "node_id": node[0],
                "domain": node[1],
                "name": node[2],
                "node_type": node[3],
                "payload": node[4],
                "created_at": node[5],
            },
            None,
        )

    def GetEdges(self, params):
        """Return outgoing edges for a node."""
        node_id = params.get("node_id")
        if not node_id:
            return (0, None, "missing_param: node_id")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        edges = cur.execute(
            "SELECT edge_id, from_node, to_node, condition, weight FROM decision_edges WHERE from_node=? ORDER BY weight DESC",
            (node_id,),
        ).fetchall()
        db.close()
        edge_list = [
            {"edge_id": e[0], "from": e[1], "to": e[2], "condition": e[3], "weight": e[4]}
            for e in edges
        ]
        return (1, {"node_id": node_id, "edges": edge_list, "count": len(edge_list)}, None)

    def Log(self, params):
        """Write to execution_log."""
        run_id = params.get("run_id")
        node_id = params.get("node_id")
        status = params.get("status", "executed")
        output = params.get("output", "")
        if not run_id or not node_id:
            return (0, None, "missing_param: run_id and node_id")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        self.WriteLog(cur, run_id, node_id, status, output)
        db.commit()
        db.close()
        return (1, {"logged": True, "run_id": run_id, "node_id": node_id}, None)

    def Status(self, params):
        """Return current node + state for a run."""
        run_id = params.get("run_id", self.state.get("run_id"))
        if not run_id:
            return (0, None, "missing_param: run_id")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        row = cur.execute(
            "SELECT current_node, state, updated_at FROM run_state WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if not row:
            db.close()
            return (0, None, "run_not_found: {rid}".format(rid=run_id))
        db.close()
        return (
            1,
            {"run_id": run_id, "current_node": row[0], "state": row[1], "updated_at": row[2]},
            None,
        )

    def History(self, params):
        """Return full execution trace for a run."""
        run_id = params.get("run_id", self.state.get("run_id"))
        if not run_id:
            return (0, None, "missing_param: run_id")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        logs = cur.execute(
            "SELECT log_id, node_id, status, output, timestamp FROM execution_log WHERE run_id=? ORDER BY log_id",
            (run_id,),
        ).fetchall()
        db.close()
        trace = [
            {"log_id": l[0], "node_id": l[1], "status": l[2], "output": l[3], "timestamp": l[4]}
            for l in logs
        ]
        return (1, {"run_id": run_id, "trace": trace, "count": len(trace)}, None)

    def ExecuteNode(self, node_id, name, node_type, payload, cur, run_id):
        """Execute a single node based on its type. Returns result dict."""
        if node_type == "question":
            self.WriteLog(cur, run_id, node_id, "executed", json.dumps({"type": "question", "awaiting": True}))
            return {"type": "question", "awaiting": True}
        if node_type == "check":
            result = {"type": "check", "pass": True}
            self.WriteLog(cur, run_id, node_id, "executed", json.dumps(result))
            return result
        if node_type == "fallback":
            result = {"type": "fallback", "recovered": True}
            self.WriteLog(cur, run_id, node_id, "executed", json.dumps(result))
            return result
        if node_type == "action":
            if payload:
                bcl_row = cur.execute(
                    "SELECT token_name, bcl_content FROM bcl_instructions WHERE token_name=?",
                    (payload,),
                ).fetchone()
                if not bcl_row:
                    self.WriteLog(cur, run_id, node_id, "failed", json.dumps({"error": "bcl_token_not_found", "payload": payload}))
                    return {"type": "action", "error": "bcl_token_not_found", "payload": payload}
                result = {"type": "action", "bcl": payload, "executed": True}
                self.WriteLog(cur, run_id, node_id, "executed", json.dumps(result))
                return result
            result = {"type": "action", "executed": True}
            self.WriteLog(cur, run_id, node_id, "executed", json.dumps(result))
            return result
        result = {"type": node_type, "executed": True}
        self.WriteLog(cur, run_id, node_id, "executed", json.dumps(result))
        return result

    def MatchesCondition(self, condition, result):
        """Check if an edge condition matches the node result."""
        if condition == "success":
            return result.get("error") is None
        if condition == "fail":
            return result.get("error") is not None
        if condition == "error":
            return result.get("error") is not None
        if condition == "true":
            return True
        if condition == "false":
            return False
        return False

    def WriteLog(self, cur, run_id, node_id, status, output):
        """Write a row to execution_log."""
        cur.execute(
            "INSERT INTO execution_log (run_id, node_id, status, output) VALUES (?, ?, ?, ?)",
            (run_id, node_id, status, output),
        )
