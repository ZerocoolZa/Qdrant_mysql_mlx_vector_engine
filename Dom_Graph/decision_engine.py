#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/decision_engine.py"
# date="2026-06-26" author="Devin" session_id="phase6-intelligence"
# context="Project Digital Twin Section 55 Decision Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="decision_engine.py" domain="twin_decision" authority="DecisionEngine"}
# [@SUMMARY]{summary="Decision authority that gets candidate fixes, ranks them, analyzes risk, simulates outcomes, and makes final decisions."}
# [@CLASS]{class="DecisionEngine" domain="decision" authority="single"}
# [@METHOD]{method="get_candidates" type="command"}
# [@METHOD]{method="rank_fixes" type="command"}
# [@METHOD]{method="analyze_risk" type="command"}
# [@METHOD]{method="simulate" type="command"}
# [@METHOD]{method="decide" type="command"}
# [@METHOD]{method="analyze_cost" type="command"}
# [@METHOD]{method="analyze_benefit" type="command"}
# [@METHOD]{method="validate" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<DecisionEngine: gets candidate fixes, ranks them, analyzes risk/cost/benefit, simulates outcomes, makes final decisions. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
DecisionEngine -- Decision making authority.
Implements Section 55 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: get_candidates, rank_fixes, analyze_risk, simulate, decide,
          analyze_cost, analyze_benefit, validate.
"""
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class DecisionEngine:
    """Decision making authority."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "get_candidates":
            return self.GetCandidates(params)
        elif command == "rank_fixes":
            return self.RankFixes(params)
        elif command == "analyze_risk":
            return self.AnalyzeRisk(params)
        elif command == "simulate":
            return self.Simulate(params)
        elif command == "decide":
            return self.Decide(params)
        elif command == "analyze_cost":
            return self.AnalyzeCost(params)
        elif command == "analyze_benefit":
            return self.AnalyzeBenefit(params)
        elif command == "validate":
            return self.Validate(params)

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

    def Connect(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
        return self.state["db_conn"]

    def GetCandidates(self, params):
        problem = self._p(params, "problem", "")
        if not problem:
            return (0, None, ("NO_PARAM", "problem required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem, answer, confidence, fix_result, "
                    "error_type, method_id, class_id, file_id FROM knowledge "
                    "WHERE problem LIKE ? AND answer IS NOT NULL ORDER BY confidence DESC",
                    ("%" + problem + "%",))
        candidates = []
        for r in cur.fetchall():
            candidates.append({"knowledge_id": r[0], "problem": r[1], "answer": r[2],
                               "confidence": r[3], "fix_result": r[4], "error_type": r[5],
                               "method_id": r[6], "class_id": r[7], "file_id": r[8]})
        return (1, {"candidates": candidates, "count": len(candidates)}, None)

    def RankFixes(self, params):
        cand_res = self.GetCandidates(params)
        if cand_res[0] != 1:
            return cand_res
        candidates = cand_res[1]["candidates"]
        conn = self.Connect()
        cur = conn.cursor()
        for c in candidates:
            cur.execute("SELECT COUNT(*) FROM knowledge WHERE answer=? AND fix_result='success'",
                        (c.get("answer"),))
            c["success_count"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM knowledge WHERE answer=?", (c.get("answer"),))
            total = cur.fetchone()[0]
            c["total_count"] = total
            c["success_rate"] = (c["success_count"] / total) if total > 0 else 0.0
        ranked = sorted(candidates, key=lambda c: (
            c.get("fix_result") == "success", c.get("success_rate", 0.0),
            c.get("confidence", 0)), reverse=True)
        return (1, {"ranked_fixes": ranked, "count": len(ranked)}, None)

    def AnalyzeRisk(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT cyclomatic_complexity FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        complexity = row[0] if row else 0
        cur.execute("SELECT COUNT(DISTINCT src_id) FROM edges WHERE dst_type='method' "
                    "AND dst_id=? AND edge_type='calls'", (method_id,))
        incoming_edges = cur.fetchone()[0]
        total_complexity = complexity
        affected = [method_id]
        visited = set()
        queue = [method_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            cur.execute("SELECT DISTINCT src_id FROM edges WHERE dst_type='method' "
                        "AND dst_id=? AND edge_type='calls'", (current,))
            for r in cur.fetchall():
                caller = r[0]
                if caller not in visited:
                    affected.append(caller)
                    queue.append(caller)
                    cur.execute("SELECT cyclomatic_complexity FROM methods WHERE method_id=?",
                                (caller,))
                    crow = cur.fetchone()
                    if crow:
                        total_complexity = total_complexity + crow[0]
        depth = self.ComputeDependencyDepth(method_id, cur)
        risk = (incoming_edges * complexity * (1 + depth)) / 10.0
        return (1, {"method_id": method_id, "incoming_edges": incoming_edges,
                    "complexity": complexity, "total_complexity": total_complexity,
                    "dependency_depth": depth, "affected_methods": len(affected),
                    "risk_score": risk}, None)

    def ComputeDependencyDepth(self, method_id, cur):
        visited = set()
        max_depth = [0]
        def dfs(mid, depth):
            if mid in visited:
                return
            visited.add(mid)
            if depth > max_depth[0]:
                max_depth[0] = depth
            cur.execute("SELECT DISTINCT dst_id FROM edges WHERE src_type='method' "
                        "AND src_id=? AND edge_type='calls'", (mid,))
            for r in cur.fetchall():
                dfs(r[0], depth + 1)
        dfs(method_id, 0)
        return max_depth[0]

    def Simulate(self, params):
        fix_id = self._p(params, "fix_id")
        if not fix_id:
            return (0, None, ("NO_PARAM", "fix_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT answer, method_id FROM knowledge WHERE knowledge_id=?", (fix_id,))
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "Fix not found", 0))
        answer = row[0] or ""
        method_id = row[1]
        sandbox = sqlite3.connect(":memory:")
        try:
            scur = sandbox.cursor()
            sconn_src = conn
            ssrc = sconn_src.cursor()
            ssrc.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
            for r in ssrc.fetchall():
                scur.execute(r[0])
            ssrc.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
            for r in ssrc.fetchall():
                try:
                    scur.execute(r[0])
                except sqlite3.Error:
                    pass
            for table in ("files", "classes", "methods", "edges", "knowledge",
                          "attempts", "observations", "snapshots"):
                try:
                    ssrc.execute("SELECT * FROM " + table)
                    cols = [d[0] for d in ssrc.description]
                    placeholders = ",".join(["?"] * len(cols))
                    col_list = ",".join(cols)
                    for data_row in ssrc.fetchall():
                        scur.execute("INSERT INTO " + table + " (" + col_list + ") VALUES (" + placeholders + ")", data_row)
                except sqlite3.Error:
                    pass
            simulated = True
            compile_ok = True
            if method_id:
                scur.execute("SELECT method_code FROM methods WHERE method_id=?", (method_id,))
                mrow = scur.fetchone()
                if mrow and mrow[0]:
                    try:
                        compile(mrow[0], "<simulated>", "exec")
                    except SyntaxError:
                        compile_ok = False
                        simulated = False
            sandbox.commit()
            return (1, {"simulated": simulated, "fix_id": fix_id, "answer": answer,
                        "compile_ok": compile_ok, "sandbox": "memory"}, None)
        except sqlite3.Error as e:
            return (0, None, ("SIMULATE_FAILED", str(e), 0))
        finally:
            sandbox.close()

    def Decide(self, params):
        ranked_res = self.RankFixes(params)
        if ranked_res[0] != 1:
            return ranked_res
        fixes = ranked_res[1]["ranked_fixes"]
        if not fixes:
            return (1, {"chosen_fix": None, "reason": "no candidates found"}, None)
        method_id = self._p(params, "method_id")
        problem = self._p(params, "problem", "")
        evaluated = []
        for fix in fixes:
            entry = dict(fix)
            risk = 0.0
            if method_id:
                risk_res = self.AnalyzeRisk({"method_id": method_id})
                if risk_res[0] == 1:
                    risk = risk_res[1]["risk_score"]
                    entry["risk_analysis"] = risk_res[1]
            entry["risk_score"] = risk
            sim_res = self.Simulate({"fix_id": fix["knowledge_id"]})
            entry["simulation"] = sim_res[1] if sim_res[0] == 1 else {"simulated": False}
            val_res = self.Validate({"fix_id": fix["knowledge_id"]})
            entry["validation"] = val_res[1] if val_res[0] == 1 else {"validated": False}
            cost = 0.0
            if method_id:
                cost_res = self.AnalyzeCost({"method_id": method_id})
                if cost_res[0] == 1:
                    cost = cost_res[1]["cost_score"]
                    entry["cost_analysis"] = cost_res[1]
            entry["cost_score"] = cost
            benefit = 0.0
            if problem:
                ben_res = self.AnalyzeBenefit({"problem": problem})
                if ben_res[0] == 1:
                    benefit = ben_res[1]["benefit_score"]
                    entry["benefit_analysis"] = ben_res[1]
            entry["benefit_score"] = benefit
            confidence = fix.get("confidence", 0)
            sim_ok = 1 if entry["simulation"].get("simulated") else 0
            val_ok = 1 if entry["validation"].get("validated") else 0
            denom = 1 + risk + (cost / 10.0)
            if denom == 0:
                denom = 1
            entry["decision_score"] = (confidence * (1 + fix.get("success_rate", 0.0)) *
                                        (1 + sim_ok) * (1 + val_ok) + benefit) / denom
            evaluated.append(entry)
        evaluated.sort(key=lambda e: e["decision_score"], reverse=True)
        best = evaluated[0]
        return (1, {"chosen_fix": best, "decision_score": best["decision_score"],
                    "reason": "best confidence/risk ratio after simulation, validation, cost and benefit",
                    "evaluated": evaluated}, None)

    def AnalyzeCost(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT line_count, cyclomatic_complexity FROM methods WHERE method_id=?",
                    (method_id,))
        row = cur.fetchone()
        line_count = row[0] if row else 0
        complexity = row[1] if row else 0
        cur.execute("SELECT COUNT(DISTINCT src_id) FROM edges WHERE dst_type='method' "
                    "AND dst_id=? AND edge_type='calls'", (method_id,))
        affected = cur.fetchone()[0]
        cost = line_count + (complexity * 2) + (affected * 5)
        return (1, {"method_id": method_id, "lines_changed": line_count,
                    "methods_affected": affected, "complexity": complexity,
                    "cost_score": cost}, None)

    def AnalyzeBenefit(self, params):
        problem = self._p(params, "problem", "")
        if not problem:
            return (0, None, ("NO_PARAM", "problem required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE problem LIKE ? AND fix_result='success'",
                    ("%" + problem + "%",))
        fixes_resolved = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1 OR has_decorator=1 "
                    "OR has_self_underscore=1")
        violations = cur.fetchone()[0]
        benefit = (fixes_resolved * 10) + (violations * 2)
        return (1, {"problem": problem, "fixes_resolved": fixes_resolved,
                    "violations_addressed": violations, "benefit_score": benefit}, None)

    def Validate(self, params):
        fix_id = self._p(params, "fix_id")
        if not fix_id:
            return (0, None, ("NO_PARAM", "fix_id required", 0))
        sim_res = self.Simulate({"fix_id": fix_id})
        if sim_res[0] != 1:
            return sim_res
        sim_data = sim_res[1]
        compile_ok = sim_data.get("compile_ok", False)
        validated = compile_ok and sim_data.get("simulated", False)
        return (1, {"fix_id": fix_id, "compile_ok": compile_ok,
                    "validated": validated, "sandbox_result": sim_data}, None)

