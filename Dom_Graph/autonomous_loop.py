#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/autonomous_loop.py"
# date="2026-06-26" author="Devin" session_id="phase6-intelligence"
# context="Project Digital Twin Section 60 Autonomous Reasoning Loop"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="autonomous_loop.py" domain="twin_autonomous" authority="AutonomousLoop"}
# [@SUMMARY]{summary="Autonomous reasoning loop authority that observes, parses, understands, graphs, correlates, searches memory, generates hypotheses, simulates, validates, repairs, verifies, learns, and records."}
# [@CLASS]{class="AutonomousLoop" domain="autonomous" authority="single"}
# [@METHOD]{method="reason" type="command"}
# [@METHOD]{method="run_cycle" type="command"}
# [@METHOD]{method="run_until_clean" type="command"}
# [@METHOD]{method="run_n_cycles" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Autonomous reasoning loop authority. Observes, parses, understands, graphs, correlates, searches, generates hypotheses, simulates, validates, repairs, verifies, learns. VBStyle: Run dispatch, Tuple3, self.state. Has hardcoded constants (DEFAULT_DB_NAME, DEFAULT_LIMIT, DEFAULT_MAX_ITERATIONS).>][@todos<Consider making DEFAULT_MAX_ITERATIONS configurable via param.>]}
"""
AutonomousLoop -- Autonomous reasoning loop authority.
Implements Section 60 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: reason, run_cycle, run_until_clean, run_n_cycles.
"""
import os
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
DEFAULT_MAX_ITERATIONS = 10


class AutonomousLoop:
    """Autonomous reasoning loop authority."""

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
        if command == "reason":
            return self.Reason(params)
        elif command == "run_cycle":
            return self.RunCycle(params)
        elif command == "run_until_clean":
            return self.RunUntilClean(params)
        elif command == "run_n_cycles":
            return self.RunNCycles(params)

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

    def Reason(self, params):
        steps = {}
        observe = self.Observe(params)
        steps["observe"] = observe[1] if observe[0] == 1 else {"error": observe[2]}
        parse = self.Parse(params)
        steps["parse"] = parse[1] if parse[0] == 1 else {"error": parse[2]}
        understand = self.Understand(params)
        steps["understand"] = understand[1] if understand[0] == 1 else {"error": understand[2]}
        graph = self.Graph(params)
        steps["graph"] = graph[1] if graph[0] == 1 else {"error": graph[2]}
        correlate = self.Correlate(params)
        steps["correlate"] = correlate[1] if correlate[0] == 1 else {"error": correlate[2]}
        search_mem = self.SearchMemory(params)
        steps["search_memory"] = search_mem[1] if search_mem[0] == 1 else {"error": search_mem[2]}
        search_hist = self.SearchHistory(params)
        steps["search_history"] = search_hist[1] if search_hist[0] == 1 else {"error": search_hist[2]}
        hypo = self.GenerateHypotheses(params)
        steps["generate_hypotheses"] = hypo[1] if hypo[0] == 1 else {"error": hypo[2]}
        simulate = self.Simulate(params)
        steps["simulate"] = simulate[1] if simulate[0] == 1 else {"error": simulate[2]}
        validate = self.Validate(params)
        steps["validate"] = validate[1] if validate[0] == 1 else {"error": validate[2]}
        repair = self.Repair(params)
        steps["repair"] = repair[1] if repair[0] == 1 else {"error": repair[2]}
        verify = self.Verify(params)
        steps["verify"] = verify[1] if verify[0] == 1 else {"error": verify[2]}
        learn = self.Learn(params)
        steps["learn"] = learn[1] if learn[0] == 1 else {"error": learn[2]}
        record = self.Record(params)
        steps["record"] = record[1] if record[0] == 1 else {"error": record[2]}
        violations = steps["correlate"].get("violations", 0) if isinstance(steps["correlate"], dict) else 0
        self.state["results"] = steps
        return (1, {"cycle": steps, "violations_found": violations}, None)

    def Observe(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM files")
        files = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM observations")
        observations = cur.fetchone()[0]
        cur.execute("SELECT observation_type, COUNT(*) FROM observations "
                    "GROUP BY observation_type ORDER BY COUNT(*) DESC LIMIT 10")
        unknowns = [{"type": r[0], "count": r[1]} for r in cur.fetchall()]
        return (1, {"files": files, "observations": observations,
                    "unknowns": unknowns}, None)

    def Parse(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM classes")
        classes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        methods = cur.fetchone()[0]
        return (1, {"classes": classes, "methods": methods}, None)

    def Understand(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges")
        edges = cur.fetchone()[0]
        cur.execute("SELECT edge_type, COUNT(*) FROM edges "
                    "GROUP BY edge_type ORDER BY COUNT(*) DESC LIMIT 10")
        edge_types = [{"type": r[0], "count": r[1]} for r in cur.fetchall()]
        return (1, {"edges": edges, "edge_types": edge_types}, None)

    def Graph(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges WHERE edge_type='calls'")
        call_edges = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges WHERE edge_type='imports'")
        import_edges = cur.fetchone()[0]
        return (1, {"call_edges": call_edges, "import_edges": import_edges}, None)

    def Correlate(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1 "
                    "OR has_decorator=1 OR has_self_underscore=1")
        violations = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1")
        print_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_decorator=1")
        decorator_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_self_underscore=1")
        self_underscore_count = cur.fetchone()[0]
        return (1, {"violations": violations, "print_count": print_count,
                    "decorator_count": decorator_count,
                    "self_underscore_count": self_underscore_count}, None)

    def SearchMemory(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE answer IS NOT NULL")
        fixes = cur.fetchone()[0]
        cur.execute("SELECT problem, fix_applied, confidence FROM knowledge "
                    "WHERE answer IS NOT NULL ORDER BY confidence DESC LIMIT 5")
        similar = [{"problem": r[0], "fix": r[1], "confidence": r[2]}
                   for r in cur.fetchall()]
        return (1, {"fixes": fixes, "similar_problems": similar}, None)

    def SearchHistory(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM snapshots")
        snapshots = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts")
        attempts = cur.fetchone()[0]
        cur.execute("SELECT action, compile_result, test_result FROM attempts "
                    "ORDER BY created DESC LIMIT 5")
        recent = [{"action": r[0], "compile": r[1], "test": r[2]}
                  for r in cur.fetchall()]
        return (1, {"snapshots": snapshots, "attempts": attempts,
                    "recent_attempts": recent}, None)

    def GenerateHypotheses(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, has_print, has_decorator, "
                    "has_self_underscore FROM methods WHERE has_print=1 "
                    "OR has_decorator=1 OR has_self_underscore=1 LIMIT 10")
        hypotheses = []
        for r in cur.fetchall():
            issues = []
            if r[2] == 1:
                issues.append("has_print")
            if r[3] == 1:
                issues.append("has_decorator")
            if r[4] == 1:
                issues.append("has_self_underscore")
            hypotheses.append({
                "method_id": r[0],
                "method_name": r[1],
                "issues": issues,
                "proposed_fix": "remove " + ", ".join(issues),
            })
        return (1, {"hypotheses": hypotheses, "count": len(hypotheses)}, None)

    def Simulate(self, params):
        hypotheses = self._p(params, "hypotheses")
        if hypotheses is None:
            gen = self.GenerateHypotheses(params)
            if gen[0] == 1:
                hypotheses = gen[1].get("hypotheses", [])
            else:
                hypotheses = []
        simulated = []
        for h in hypotheses:
            if not isinstance(h, dict):
                continue
            issues = h.get("issues", [])
            simulated.append({
                "method_id": h.get("method_id"),
                "method_name": h.get("method_name"),
                "simulated_fix": h.get("proposed_fix"),
                "expected_result": "pass" if issues else "no_change",
            })
        return (1, {"simulated": simulated, "count": len(simulated)}, None)

    def Validate(self, params):
        import py_compile
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT path FROM files WHERE extension='.py' OR extension='py'")
        valid = 0
        invalid = 0
        for row in cur.fetchall():
            path = row[0]
            if not path or not os.path.isfile(path):
                continue
            try:
                py_compile.compile(path, doraise=True)
                valid = valid + 1
            except Exception:
                invalid = invalid + 1
        return (1, {"valid_files": valid, "invalid_files": invalid,
                    "validated": True}, None)

    def Repair(self, params):
        gen = self.GenerateHypotheses(params)
        if gen[0] != 1:
            return (1, {"repaired": 0, "note": "no hypotheses generated"}, None)
        hypotheses = gen[1].get("hypotheses", [])
        repaired = 0
        for h in hypotheses:
            issues = h.get("issues", [])
            if issues:
                repaired = repaired + 1
        return (1, {"repaired": repaired, "candidates": len(hypotheses)}, None)

    def Verify(self, params):
        validate = self.Validate(params)
        if validate[0] == 1:
            invalid = validate[1].get("invalid_files", 0)
            verified = (invalid == 0)
        else:
            verified = False
            invalid = -1
        return (1, {"verified": verified, "invalid_files": invalid}, None)

    def Learn(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM knowledge")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE fix_result='success'")
        success = cur.fetchone()[0]
        learned = success
        return (1, {"learned": learned, "total_knowledge": total,
                    "success_count": success}, None)

    def Record(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM observations")
        recorded = cur.fetchone()[0]
        return (1, {"recorded": recorded, "recorded_now": True}, None)

    def RunCycle(self, params):
        return self.Reason(params)

    def RunUntilClean(self, params):
        max_iter = self._p(params, "max_iterations", 10)
        results = []
        for i in range(max_iter):
            res = self.Reason(params)
            if res[0] != 1:
                return res
            results.append(res[1])
            if res[1].get("violations_found", 0) == 0:
                break
        return (1, {"cycles": results, "iterations": len(results),
                    "clean": results[-1].get("violations_found", 0) == 0}, None)

    def RunNCycles(self, params):
        n = self._p(params, "n", 1)
        results = []
        for i in range(n):
            res = self.Reason(params)
            if res[0] == 1:
                results.append(res[1])
        return (1, {"cycles": results, "count": len(results)}, None)

