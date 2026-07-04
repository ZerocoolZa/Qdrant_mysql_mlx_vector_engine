#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/confidence_engine.py"
# date="2026-06-26" author="Devin" session_id="phase-orchestration"
# context="Project Digital Twin Section 30 Confidence Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="confidence_engine.py" domain="twin_confidence" authority="ConfidenceEngine"}
# [@SUMMARY]{summary="Confidence authority that computes parse, match, graph, repair, test, and overall confidence scores."}
# [@CLASS]{class="ConfidenceEngine" domain="confidence" authority="single"}
# [@METHOD]{method="parse_confidence" type="command"}
# [@METHOD]{method="match_confidence" type="command"}
# [@METHOD]{method="graph_confidence" type="command"}
# [@METHOD]{method="repair_confidence" type="command"}
# [@METHOD]{method="runtime_confidence" type="command"}
# [@METHOD]{method="test_confidence" type="command"}
# [@METHOD]{method="overall_confidence" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<ConfidenceEngine: computes parse/match/graph/repair/runtime/test/overall confidence scores. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
ConfidenceEngine -- Confidence scoring authority.
Implements Section 30 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: parse_confidence, match_confidence, graph_confidence, repair_confidence,
          runtime_confidence, test_confidence, overall_confidence.
Uses REAL queries against knowledge/observations/attempts tables and REAL math
(weighted averages, success rate calculations).
"""
import ast
import os
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class ConfidenceEngine:
    """Confidence scoring authority."""

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
        if command == "parse_confidence":
            return self.ParseConfidence(params)
        elif command == "match_confidence":
            return self.MatchConfidence(params)
        elif command == "graph_confidence":
            return self.GraphConfidence(params)
        elif command == "repair_confidence":
            return self.RepairConfidence(params)
        elif command == "runtime_confidence":
            return self.RuntimeConfidence(params)
        elif command == "test_confidence":
            return self.TestConfidence(params)
        elif command == "overall_confidence":
            return self.OverallConfidence(params)

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

    def ParseConfidence(self, params):
        # 30.1 Parse Confidence: 100 if AST parse succeeds, 0 if fails
        # Also extracts confidence values from knowledge/observations tables
        file_path = self._p(params, "file_path")
        file_id = self._p(params, "file_id")
        conn = self.Connect()
        cur = conn.cursor()
        if file_id:
            cur.execute("SELECT path FROM files WHERE file_id=?", (file_id,))
            row = cur.fetchone()
            if not row:
                return (0, None, ("NOT_FOUND", "file not found", 0))
            file_path = row[0]
        parse_score = 0
        if file_path and os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                ast.parse(content, filename=file_path)
                parse_score = 100
            except SyntaxError:
                parse_score = 0
        # extract average confidence from knowledge table
        cur.execute("SELECT AVG(confidence) FROM knowledge WHERE confidence IS NOT NULL")
        knowledge_conf = cur.fetchone()[0] or 0
        # extract average confidence from observations table
        obs_conf = 0
        try:
            cur.execute("SELECT AVG(confidence) FROM observations WHERE confidence IS NOT NULL")
            obs_conf = cur.fetchone()[0] or 0
        except sqlite3.Error:
            obs_conf = 0
        # weighted: parse score 60%, knowledge confidence 20%, observations 20%
        if file_path:
            overall = parse_score * 0.6 + knowledge_conf * 0.2 + obs_conf * 0.2
        else:
            overall = knowledge_conf * 0.5 + obs_conf * 0.5
        return (1, {"parse_confidence": overall, "ast_parse_score": parse_score,
                    "knowledge_confidence": knowledge_conf,
                    "observation_confidence": obs_conf}, None)

    def MatchConfidence(self, params):
        # 30.2 Match Confidence: similarity score 0-100 when matching patterns
        # Also compares confidence between similar errors in knowledge table
        pattern = self._p(params, "pattern", "")
        target = self._p(params, "target", "")
        error_type = self._p(params, "error_type")
        conn = self.Connect()
        cur = conn.cursor()
        text_score = 0
        if pattern and target:
            # character-level similarity
            matching = sum(1 for a, b in zip(pattern, target) if a == b)
            text_score = (matching / max(len(pattern), len(target))) * 100
        # query knowledge for similar errors and compare confidence values
        similar_confidences = []
        if error_type:
            cur.execute("SELECT confidence, problem FROM knowledge WHERE error_type=? "
                        "ORDER BY confidence DESC LIMIT 10", (error_type,))
            for row in cur.fetchall():
                similar_confidences.append({"confidence": row[0], "problem": row[1]})
        if similar_confidences:
            avg_conf = sum(c["confidence"] for c in similar_confidences) / len(similar_confidences)
        else:
            avg_conf = 0
        # combined match confidence: text similarity 50%, similar error confidence 50%
        if pattern and similar_confidences:
            match_score = text_score * 0.5 + avg_conf * 0.5
        elif pattern:
            match_score = text_score
        else:
            match_score = avg_conf
        return (1, {"match_confidence": match_score, "text_similarity": text_score,
                    "similar_error_avg_confidence": avg_conf,
                    "similar_errors_count": len(similar_confidences)}, None)

    def GraphConfidence(self, params):
        # 30.3 Graph Confidence: percentage of entities with edges + confidence distribution
        conn = self.Connect()
        cur = conn.cursor()
        # count entities with edges vs total entities
        cur.execute("SELECT COUNT(DISTINCT src_id) + COUNT(DISTINCT dst_id) FROM edges")
        graph_entities = cur.fetchone()[0] or 0
        total = 0
        for table in ("files", "classes", "methods"):
            cur.execute("SELECT COUNT(*) FROM " + table)
            total += cur.fetchone()[0]
        coverage_pct = (graph_entities / total * 100) if total > 0 else 0
        # compute confidence distribution across edges
        cur.execute("SELECT AVG(confidence), MIN(confidence), MAX(confidence) FROM edges")
        row = cur.fetchone()
        avg_edge_conf = row[0] or 0
        min_edge_conf = row[1] or 0
        max_edge_conf = row[2] or 0
        # distribution by edge type
        cur.execute("SELECT edge_type, AVG(confidence), COUNT(*) FROM edges GROUP BY edge_type")
        distribution = {}
        for et_row in cur.fetchall():
            distribution[et_row[0]] = {"avg_confidence": et_row[1], "count": et_row[2]}
        # graph confidence: coverage 60%, avg edge confidence 40%
        graph_conf = coverage_pct * 0.6 + avg_edge_conf * 0.4
        return (1, {"graph_confidence": round(graph_conf, 2),
                    "coverage_pct": round(coverage_pct, 2),
                    "avg_edge_confidence": round(avg_edge_conf, 2),
                    "min_edge_confidence": min_edge_conf,
                    "max_edge_confidence": max_edge_conf,
                    "distribution": distribution}, None)

    def RepairConfidence(self, params):
        # 30.4 Repair Confidence: confidence in a fix based on past success rate
        error_type = self._p(params, "error_type")
        conn = self.Connect()
        cur = conn.cursor()
        # overall success rate from knowledge table
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE answer IS NOT NULL")
        total_fixes = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE fix_result='success'")
        successful = cur.fetchone()[0] or 0
        overall_success_rate = (successful / total_fixes * 100) if total_fixes > 0 else 0
        # per-error-type success rate
        type_success_rate = overall_success_rate
        if error_type:
            cur.execute("SELECT COUNT(*) FROM knowledge WHERE error_type=? AND answer IS NOT NULL", (error_type,))
            type_total = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(*) FROM knowledge WHERE error_type=? AND fix_result='success'", (error_type,))
            type_success = cur.fetchone()[0] or 0
            type_success_rate = (type_success / type_total * 100) if type_total > 0 else 0
        # attempts table success rate
        attempts_success_rate = 0
        try:
            cur.execute("SELECT COUNT(*) FROM attempts")
            attempts_total = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(*) FROM attempts WHERE compile_result=1 AND test_result=1")
            attempts_success = cur.fetchone()[0] or 0
            attempts_success_rate = (attempts_success / attempts_total * 100) if attempts_total > 0 else 0
        except sqlite3.Error:
            pass
        # weighted: type-specific 50%, overall 25%, attempts 25%
        if error_type:
            repair_conf = type_success_rate * 0.5 + overall_success_rate * 0.25 + attempts_success_rate * 0.25
        else:
            repair_conf = overall_success_rate * 0.6 + attempts_success_rate * 0.4
        return (1, {"repair_confidence": round(repair_conf, 2),
                    "overall_success_rate": round(overall_success_rate, 2),
                    "type_success_rate": round(type_success_rate, 2),
                    "attempts_success_rate": round(attempts_success_rate, 2),
                    "total_fixes": total_fixes,
                    "successful_fixes": successful}, None)

    def RuntimeConfidence(self, params):
        # 30.5 Runtime Confidence: based on test pass rate and runtime observations
        conn = self.Connect()
        cur = conn.cursor()
        # count confirmed vs unconfirmed observations
        confirmed = 0
        total_obs = 0
        try:
            cur.execute("SELECT COUNT(*) FROM observations")
            total_obs = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(*) FROM observations WHERE observation_type='confirmed'")
            confirmed = cur.fetchone()[0] or 0
        except sqlite3.Error:
            pass
        obs_confidence = (confirmed / total_obs * 100) if total_obs > 0 else 0
        # count methods with Run() and Tuple3 returns (runtime-ready)
        cur.execute("SELECT COUNT(*) FROM methods")
        total_methods = cur.fetchone()[0] or 1
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_run_method=1 AND returns_tuple3=1")
        runtime_ready = cur.fetchone()[0] or 0
        runtime_coverage = (runtime_ready / total_methods * 100) if total_methods > 0 else 0
        # weighted: observation confidence 40%, runtime coverage 60%
        runtime_conf = obs_confidence * 0.4 + runtime_coverage * 0.6
        return (1, {"runtime_confidence": round(runtime_conf, 2),
                    "observation_confidence": round(obs_confidence, 2),
                    "runtime_coverage": round(runtime_coverage, 2),
                    "confirmed_observations": confirmed,
                    "total_observations": total_obs,
                    "runtime_ready_methods": runtime_ready}, None)

    def TestConfidence(self, params):
        # 30.6 Test Confidence: passed/total tests * 100
        import subprocess
        cwd = os.path.dirname(os.path.abspath(__file__))
        # first check attempts table for historical test results
        conn = self.Connect()
        cur = conn.cursor()
        historical_pass = 0
        historical_total = 0
        try:
            cur.execute("SELECT COUNT(*) FROM attempts WHERE test_result IS NOT NULL")
            historical_total = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(*) FROM attempts WHERE test_result=1")
            historical_pass = cur.fetchone()[0] or 0
        except sqlite3.Error:
            pass
        # run test suite if available
        passed = 0
        total = 0
        try:
            result = subprocess.run(["python3", "test_everything.py"], capture_output=True, text=True, cwd=cwd, timeout=60)
            output = result.stdout
            for line in output.split("\n"):
                if "RESULTS:" in line and "passed" in line:
                    try:
                        passed = int(line.split("passed")[0].split(":")[-1].strip())
                    except ValueError:
                        pass
                    if "failed" in line:
                        try:
                            failed = int(line.split("failed")[0].split(",")[-1].strip())
                            total = passed + failed
                        except ValueError:
                            total = passed
        except Exception:
            pass
        live_score = (passed / total * 100) if total > 0 else 0
        historical_score = (historical_pass / historical_total * 100) if historical_total > 0 else 0
        # weighted: live 70%, historical 30% (if live available)
        if total > 0:
            score = live_score * 0.7 + historical_score * 0.3
        else:
            score = historical_score
        return (1, {"test_confidence": round(score, 2),
                    "live_test_score": round(live_score, 2),
                    "historical_test_score": round(historical_score, 2),
                    "passed": passed, "total": total,
                    "historical_pass": historical_pass,
                    "historical_total": historical_total}, None)

    def OverallConfidence(self, params):
        # 30.7 Overall Confidence: weighted average of all confidence signals
        parse = self.ParseConfidence(params)
        match = self.MatchConfidence(params)
        graph = self.GraphConfidence(params)
        repair = self.RepairConfidence(params)
        runtime = self.RuntimeConfidence(params)
        test = self.TestConfidence(params)
        p = parse[1].get("parse_confidence", 0) if parse[0] == 1 else 0
        m = match[1].get("match_confidence", 0) if match[0] == 1 else 0
        g = graph[1].get("graph_confidence", 0) if graph[0] == 1 else 0
        r = repair[1].get("repair_confidence", 0) if repair[0] == 1 else 0
        rt = runtime[1].get("runtime_confidence", 0) if runtime[0] == 1 else 0
        t = test[1].get("test_confidence", 0) if test[0] == 1 else 0
        # weighted average: parse 15%, match 10%, graph 20%, repair 20%, runtime 15%, test 20%
        overall = p * 0.15 + m * 0.10 + g * 0.20 + r * 0.20 + rt * 0.15 + t * 0.20
        return (1, {"overall_confidence": round(overall, 2),
                    "parse": round(p, 2), "match": round(m, 2),
                    "graph": round(g, 2), "repair": round(r, 2),
                    "runtime": round(rt, 2), "test": round(t, 2)}, None)

